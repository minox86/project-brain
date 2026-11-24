import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, run_cli
from test_gitops import GitRepoCase, git


def sources(schedule):
    return {".pb/schema/sources.md": f'---\nroutine: {{branch: main, schedule: "{schedule}"}}\n---\n# Sources\n'}


class ScheduleValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def check(self, schedule):
        repo = make_brain(Path(self.tmp.name) / schedule.replace(" ", "_").replace("/", "s").replace("*", "x"),
                          sources(schedule))
        return run_cli("validate", cwd=repo)

    def test_valid_schedules(self):
        for cron in ("0 2 * * *", "30 */4 * * *", "0 8,13,18 * * 1-5", "15 6 * * 1"):
            with self.subTest(cron=cron):
                code, data, _ = self.check(cron)
                self.assertEqual(code, 0, data)

    def test_more_often_than_hourly_or_malformed(self):
        for cron in ("*/30 * * * *", "0,30 * * * *", "* 2 * * *", "0 2 * *", "61 2 * * *", "every night"):
            with self.subTest(cron=cron):
                code, data, _ = self.check(cron)
                self.assertEqual(code, 1, data)
                self.assertEqual([(e["path"], e["code"]) for e in data["errors"]],
                                 [(".pb/schema/sources.md", "bad-schedule")])

    def test_routine_without_vendored_instructions_warns(self):
        code, data, _ = self.check("0 2 * * *")
        self.assertEqual(code, 0, data)
        self.assertEqual([(w["path"], w["code"]) for w in data["warnings"]],
                         [(".pb/schema/sources.md", "routine-instructions-missing")])

    def weekly(self, schedule, vendored=False):
        files = {".pb/schema/sources.md": f'---\nreview: {{schedule: "{schedule}"}}\n---\n# Sources\n'}
        if vendored:
            files[".pb/toolkit/skills/review/SKILL.md"] = "x"
        repo = make_brain(Path(self.tmp.name) / f"weekly{len(list(Path(self.tmp.name).iterdir()))}", files)
        return run_cli("validate", cwd=repo)

    def test_weekly_review_schedule_is_checked(self):
        code, data, _ = self.weekly("*/30 * * * *")
        self.assertEqual(code, 1)
        self.assertEqual([e["code"] for e in data["errors"]], ["bad-schedule"])
        for cron in ("0 4 * * 0", "30 22 * * 7", "0 4 1 * *"):
            code, data, _ = self.weekly(cron, vendored=True)
            self.assertEqual((code, data["warnings"]), (0, []), (cron, data))

    def test_weekly_review_runs_at_most_once_a_week(self):
        for cron in ("0 4 * * *", "0 4 * * 1,4", "0 4 * * 1-5", "0 * * * 0", "0 4,16 * * 0", "0 4 1 * 0",
                     "0 4 */2 * *", "0 4 * * 9", "0 25 * * 0"):
            code, data, _ = self.weekly(cron, vendored=True)
            self.assertEqual((code, [e["code"] for e in data["errors"]]), (1, ["bad-schedule"]), (cron, data))
            self.assertIn("more than once", data["errors"][0]["message"])

    def test_weekly_review_without_vendored_instructions_warns(self):
        code, data, _ = self.weekly("0 4 * * 0")
        self.assertEqual(code, 0, data)
        self.assertEqual([w["code"] for w in data["warnings"]], ["routine-instructions-missing"])

    def test_no_routine_configured_is_fine(self):
        repo = make_brain(self.tmp.name)
        code, _, _ = run_cli("validate", cwd=repo)
        self.assertEqual(code, 0)


class LocalRunTest(GitRepoCase):
    def test_worktree_run_leaves_checkout_untouched_and_pushes(self):
        git(self.repo, "checkout", "-qb", "feat/wip")
        self.write("apps/web/wip.ts", "uncommitted\n")
        wt = Path(self.tmp.name) / "run"
        code, data, err = run_cli("routine", "start", "--branch", "docs/brain", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data["brain"], str((wt / "brain").resolve()))
        self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/wip")
        self.assertTrue((self.repo / "apps/web/wip.ts").is_file())

        self.add_page("From routine", root=wt)
        code, data, err = run_cli("--brain", wt / "brain", "routine", "finish", "--branch", "docs/brain",
                                  "-m", "manual", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual({k: data[k] for k in ("committed", "pushed", "conflict", "pr", "watched", "problems")},
                         {"committed": True, "pushed": True, "conflict": False, "pr": None, "watched": [],
                          "problems": ["no GitHub repo (github.repo in sources.md): the brain PR from "
                                       "docs/brain to main was not opened"]})
        self.assertEqual(git(self.remote, "log", "--format=%s", "-2", "docs/brain").splitlines(),
                         ["pb(routine): manual", "init"])
        self.assertIn("brain/README.md",
                      git(self.remote, "show", "--name-only", "--format=", "docs/brain").splitlines())

        code, data, err = run_cli("routine", "cleanup", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertFalse(wt.exists())
        self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/wip")

    def test_worktree_start_on_existing_branch(self):
        git(self.repo, "push", "-q", "origin", "main:refs/heads/docs/brain")
        wt = Path(self.tmp.name) / "run2"
        code, data, err = run_cli("routine", "start", "--branch", "docs/brain", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertFalse(data["created"])
        self.assertEqual(git(wt, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/docs/brain"))

    def test_cleanup_needs_worktree(self):
        code, _, _ = run_cli("routine", "cleanup", cwd=self.repo)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()


class MeetingsSourceTest(unittest.TestCase):
    def test_meetings_cursor_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp)
            code, _, err = run_cli("state", "set", "meetings", "refinement", '{"cursor": "2026-10-30T16:00:00Z"}', cwd=repo)
            self.assertEqual(code, 0, err)
            code, data, _ = run_cli("state", "get", "meetings", "refinement", cwd=repo)
            self.assertEqual(data["value"], {"cursor": "2026-10-30T16:00:00Z"})

    def test_preset_and_routine_prompt_know_meetings(self):
        from helpers import ROOT
        self.assertIn("meetings: []", (ROOT / "presets/software-product/sources.md").read_text())
        self.assertIn("`teams confluence github jira meetings questions --digest`",
                      (ROOT / "templates/routine/prompt.md").read_text())

    def test_routine_prompt_follows_the_one_pr_model(self):
        from helpers import ROOT
        text = (ROOT / "templates/routine/prompt.md").read_text()
        self.assertIn("never merge branches; never open pull requests any other way", text)
        for key in ("`pr`", "`watched`", "`behind`", "`conflict`", "`problems`", "/pb:merge"):
            self.assertIn(key, text)

    def test_cut_teams_messages_and_untouched_over_budget_pages(self):
        from helpers import ROOT
        reader = (ROOT / "references/reader.md").read_text()
        sync = (ROOT / "skills/sync/SKILL.md").read_text()
        # A cut root is read whole; a cut reply cannot be, and is reported with its link instead of trusted.
        for needle in ("`bodyTruncated: true`", "a cut **root**", "a cut **reply**", "CUT <ref> <webUrl of the message>"):
            self.assertIn(needle, reader)
        self.assertIn("`CUT` lines", sync)
        # Over budget: condense, then split; a page the run did not touch is not a problem of the run.
        self.assertIn("**split**", (ROOT / "references/writing.md").read_text())
        self.assertIn("never goes under \"Problems\"", sync)
        self.assertIn("is not a problem to report", (ROOT / "templates/routine/prompt.md").read_text())
