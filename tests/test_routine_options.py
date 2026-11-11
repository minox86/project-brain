import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, run_cli
from test_gitops import GitRepoCase, git


def sources(schedule):
    return {"schema/sources.md": f'---\nroutine: {{branch: main, schedule: "{schedule}"}}\n---\n# Sources\n'}


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
                                 [("schema/sources.md", "bad-schedule")])

    def test_routine_without_vendored_instructions_warns(self):
        code, data, _ = self.check("0 2 * * *")
        self.assertEqual(code, 0, data)
        self.assertEqual([(w["path"], w["code"]) for w in data["warnings"]],
                         [("schema/sources.md", "routine-instructions-missing")])

    def test_no_routine_configured_is_fine(self):
        repo = make_brain(self.tmp.name)
        code, _, _ = run_cli("validate", cwd=repo)
        self.assertEqual(code, 0)


class LocalRunTest(GitRepoCase):
    def test_worktree_run_leaves_checkout_untouched_and_pushes(self):
        git(self.repo, "checkout", "-qb", "feat/wip")
        self.write("apps/web/wip.ts", "uncommitted\n")
        wt = Path(self.tmp.name) / "run"
        code, data, err = run_cli("routine", "start", "--branch", "brain/inbox", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data["brain"], str((wt / "brain").resolve()))
        self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/wip")
        self.assertTrue((self.repo / "apps/web/wip.ts").is_file())

        self.add_page("From routine", root=wt)
        code, data, err = run_cli("--brain", wt / "brain", "routine", "finish", "--branch", "brain/inbox",
                                  "-m", "pb(routine): manual", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual({k: data[k] for k in ("committed", "pushed", "conflict", "pr", "watched", "problems")},
                         {"committed": True, "pushed": True, "conflict": False, "pr": None, "watched": [],
                          "problems": []})
        self.assertEqual(git(self.remote, "log", "--format=%s", "-2", "brain/inbox").splitlines(),
                         ["pb(generate): refresh generated files", "pb(routine): manual"])

        code, data, err = run_cli("routine", "cleanup", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertFalse(wt.exists())
        self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/wip")

    def test_worktree_start_on_existing_branch(self):
        git(self.repo, "push", "-q", "origin", "main:refs/heads/brain/inbox")
        wt = Path(self.tmp.name) / "run2"
        code, data, err = run_cli("routine", "start", "--branch", "brain/inbox", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertFalse(data["created"])
        self.assertEqual(git(wt, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/brain/inbox"))

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
        self.assertIn("`teams confluence github jira meetings --digest`",
                      (ROOT / "templates/routine/prompt.md").read_text())

    def test_routine_prompt_follows_the_one_pr_model(self):
        from helpers import ROOT
        text = (ROOT / "templates/routine/prompt.md").read_text()
        self.assertIn("never merge branches; never open pull requests any other way", text)
        for key in ("`pr`", "`watched`", "`behind`", "`conflict`", "`problems`", "/pb:merge"):
            self.assertIn(key, text)
