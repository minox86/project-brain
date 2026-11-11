import unittest
from pathlib import Path
from unittest import mock

from helpers import page, run_cli
from pb_core.merge import merge_land
from test_gitops import GitRepoCase, git

SRC = 'sources: ["jira:FIN-1"]'
A = "brain/functional/features/A.md"
R = "brain/decisions/R.md"
D = "brain/functional/concepts/D.md"


class MergeCase(GitRepoCase):
    """docs/brain created from main on origin; the checkout stays on main."""

    def setUp(self):
        super().setUp()
        self.put("feature", "A")
        run_cli("generate", cwd=self.repo)
        self.commit_all("A", "main")
        git(self.repo, "push", "-q", "origin", "main:refs/heads/docs/brain")
        self.worktree = Path(self.tmp.name) / "merge"

    def put(self, type_, title, meta="", body="Body.\n", root=None):
        rel, text = page(type_, title, meta, body)
        self.write("brain/" + rel, text, root)
        return "brain/" + rel

    def commit_all(self, message, branch):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", message)
        git(self.repo, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")

    def on_brain_branch(self, change):
        """Commit `change()` on docs/brain and push it; back on main afterwards."""
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "checkout", "-q", "-B", "docs/brain", "origin/docs/brain")
        change()
        run_cli("generate", cwd=self.repo)
        self.commit_all("routine", "docs/brain")
        git(self.repo, "checkout", "-q", "main")

    def on_main(self, change):
        change()
        run_cli("generate", cwd=self.repo)
        self.commit_all("developer", "main")

    def both_sides(self):
        """docs/brain edits A and adds decision R; main edits A differently and adds concept D."""
        def routine():
            self.put("feature", "A", body="Routine body.\n")
            self.put("decision", "R", f"area: technical\n{SRC}")
        self.on_brain_branch(routine)

        def developer():
            self.put("feature", "A", body="Developer body.\n")
            self.put("concept", "D", f"term_en: D\n{SRC}")
        self.on_main(developer)

    def start_cli(self):
        return run_cli("merge", "start", "--worktree", self.worktree, cwd=self.repo)

    def start(self):
        code, out, err = self.start_cli()
        self.assertEqual(code, 0, (out, err))
        return out

    def finish_cli(self):
        return run_cli("merge", "finish", "--worktree", self.worktree, "-m", "pb(merge): bring main into docs/brain",
                       cwd=self.repo)

    def remote_sha(self, branch):
        return git(self.remote, "rev-parse", branch)


class MergeStartTest(MergeCase):
    def test_start_reports_both_sides_and_classifies_conflicts(self):
        self.both_sides()
        out = self.start()
        self.assertIsNone(out["alert"])
        self.assertEqual(out["files"], [])
        self.assertEqual(out["conflicts"]["pages"], [A])
        self.assertIn("brain/index.md", out["conflicts"]["generated"])
        self.assertEqual(out["conflicts"]["schema"], [])
        self.assertIn(R, out["changed"]["routine"])
        self.assertIn(A, out["changed"]["routine"])
        self.assertNotIn("brain/index.md", out["changed"]["routine"])
        self.assertIn(D, out["changed"]["default"])
        self.assertEqual((out["behind"], out["ahead"]), (1, 1))
        self.assertEqual(out["worktree"], str(self.worktree.resolve()))
        self.assertEqual(out["brain"], str(self.worktree.resolve() / "brain"))
        self.assertEqual(out["base"], git(self.repo, "merge-base", "origin/main", "origin/docs/brain"))
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")  # the checkout is untouched
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_state_conflict_keeps_docs_brain_side(self):
        state = "brain/.pb/state/teams.json"
        self.on_brain_branch(lambda: self.write(state, '{"cursor": "routine"}\n'))
        self.on_main(lambda: self.write(state, '{"cursor": "developer"}\n'))
        out = self.start()
        self.assertEqual(out["conflicts"]["state"], [state])
        self.assertEqual((self.worktree / state).read_text(), '{"cursor": "routine"}\n')
        code, done, err = self.finish_cli()
        self.assertEqual(code, 0, (done, err))
        self.assertEqual(done["unresolved"], [])
        self.assertEqual(git(self.remote, "show", f"docs/brain:{state}"), '{"cursor": "routine"}')

    def test_schema_conflict_is_listed_never_resolved(self):
        schema = "brain/schema/brain.md"
        text = (self.repo / schema).read_text()
        self.on_brain_branch(lambda: self.write(schema, text + "\nRoutine line.\n"))
        self.on_main(lambda: self.write(schema, text + "\nDeveloper line.\n"))
        out = self.start()
        self.assertEqual(out["conflicts"]["schema"], [schema])
        self.assertEqual(out["conflicts"]["pages"], [])
        before = self.remote_sha("docs/brain")
        code, done, _ = self.finish_cli()
        self.assertEqual(code, 1)
        self.assertEqual(done["unresolved"], [schema])
        self.assertFalse(done["pushed"])
        self.assertEqual(self.remote_sha("docs/brain"), before)

    def test_start_alerts_when_docs_brain_carries_code(self):
        def routine():
            self.put("decision", "R", f"area: technical\n{SRC}")
            self.write("src/app.py", "print('x')\n")
        self.on_brain_branch(routine)
        self.on_main(lambda: self.put("concept", "D", f"term_en: D\n{SRC}"))
        before = self.remote_sha("docs/brain")
        code, out, _ = self.start_cli()
        self.assertEqual(code, 1)
        self.assertEqual(out["alert"], "outside-brain")
        self.assertEqual(out["files"], ["src/app.py"])
        self.assertEqual(self.remote_sha("docs/brain"), before)
        self.assertFalse(self.worktree.exists())

    def test_start_ignores_code_only_on_main(self):
        self.on_brain_branch(lambda: self.put("decision", "R", f"area: technical\n{SRC}"))
        self.on_main(lambda: self.write("src/app.py", "print('x')\n"))
        out = self.start()
        self.assertIsNone(out["alert"])
        self.assertEqual(out["conflicts"], {"pages": [], "schema": [], "generated": [], "state": []})


class MergeFinishTest(MergeCase):
    def test_finish_refuses_while_pages_are_unresolved(self):
        self.both_sides()
        self.start()
        before = self.remote_sha("docs/brain")
        code, out, _ = self.finish_cli()
        self.assertEqual(code, 1)
        self.assertEqual(out["unresolved"], [A])
        self.assertFalse(out["committed"])
        self.assertFalse(out["pushed"])
        self.assertEqual(self.remote_sha("docs/brain"), before)

    def resolve_a(self, body="Routine body.\n\nDeveloper body.\n", meta=""):
        self.put("feature", "A", meta, body, root=self.worktree)
        git(self.worktree, "add", A)

    def test_finish_regenerates_validates_commits_merge_and_pushes(self):
        self.both_sides()
        self.start()
        self.resolve_a()
        code, out, err = self.finish_cli()
        self.assertEqual(code, 0, (out, err))
        self.assertEqual((out["committed"], out["pushed"]), (True, True))
        self.assertEqual((out["errors"], out["unresolved"], out["problems"]), ([], [], []))
        git(self.repo, "fetch", "-q", "origin")
        self.assertEqual(git(self.repo, "rev-list", "--count", "origin/docs/brain..origin/main"), "0")
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s", "origin/docs/brain"),
                         "pb(merge): bring main into docs/brain")
        index = git(self.repo, "show", "origin/docs/brain:brain/index.md")
        for title in ("A", "R", "D"):
            self.assertIn(f"[[{title}]]", index)
        self.assertIn("Developer body.", git(self.repo, "show", f"origin/docs/brain:{A}"))
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/main"))

    def test_finish_blocks_on_invalid_resolved_page(self):
        self.both_sides()
        self.start()
        self.resolve_a(meta="status: nonsense")
        before = self.remote_sha("docs/brain")
        code, out, _ = self.finish_cli()
        self.assertEqual(code, 1)
        self.assertEqual(out["errors"][0]["path"], "functional/features/A.md")
        self.assertEqual((out["committed"], out["pushed"]), (False, False))
        self.assertEqual(self.remote_sha("docs/brain"), before)


PR = {"number": 9, "html_url": "https://github.com/o/r/pull/9", "head": {"sha": "abc123"},
      "requested_reviewers": [{"login": "lead"}], "requested_teams": []}


class LandGh:
    """Stands in for repo.gh_json during merge_land: answers like the GitHub REST API."""

    def __init__(self, checks=(("validate", "completed", "success"),), state="clean", open_prs=(PR,),
                 allow_merge_commit=True):
        self.calls = []
        self.checks = [list(c) for c in checks]
        self.state = state
        self.open_prs = list(open_prs)
        self.allow_merge_commit = allow_merge_commit

    def __call__(self, args):
        self.calls.append(list(args))
        path = args[1]
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        fields = [args[i + 1] for i, a in enumerate(args) if a == "-f"]
        if path.startswith("repos/o/r/pulls?"):
            return self.open_prs
        if method == "POST" and path == "repos/o/r/pulls":
            return {"number": 7, "html_url": "https://github.com/o/r/pull/7"}
        if path.endswith("/check-runs"):
            return {"check_runs": [{"name": n, "status": s, "conclusion": c} for n, s, c in self.checks]}
        if path.endswith("/merge") and method == "PUT":
            if "merge_method=merge" in fields and not self.allow_merge_commit:
                return None
            return {"merged": True, "sha": "def456"}
        if path.startswith("repos/o/r/pulls/"):
            return dict(PR, mergeable_state=self.state, number=int(path.rsplit("/", 1)[1]))
        if path == "repos/o/r":
            return {"allow_merge_commit": self.allow_merge_commit, "allow_squash_merge": True}
        return {}

    def merges(self):
        return [[args[i + 1] for i, a in enumerate(args) if a == "-f"]
                for args in self.calls if args[1].endswith("/merge")]


class MergeLandTest(MergeCase):
    def setUp(self):
        super().setUp()
        self.write("brain/schema/sources.md", "---\ngithub: {repo: o/r}\n---\n# Sources\n")
        self.commit_all("sources", "main")
        self.on_brain_branch(lambda: self.put("decision", "R", f"area: technical\n{SRC}"))
        self.sleeps = []

    def land(self, gh, wait=600):
        with mock.patch("pb_core.repo.gh_json", gh), mock.patch("pb_core.merge.gh_json", gh):
            return merge_land(self.repo, wait=wait, sleep=self.sleeps.append)

    def test_land_merges_when_checks_pass(self):
        gh = LandGh()
        out = self.land(gh)
        self.assertEqual(out, {"merged": True, "pr": PR["html_url"], "missing": [], "problems": []})
        self.assertEqual(gh.merges(), [["merge_method=merge", "sha=abc123"]])
        self.assertEqual(gh.calls[0][1], "repos/o/r/pulls?head=o:docs/brain&base=main&state=open")
        self.assertFalse([c for c in gh.calls if "PATCH" in c])  # the routine's description is kept
        self.assertEqual(self.sleeps, [])

    def test_land_opens_the_pr_when_none_is_open(self):
        gh = LandGh(open_prs=())
        out = self.land(gh)
        self.assertTrue(out["merged"])
        self.assertEqual(out["pr"], "https://github.com/o/r/pull/7")
        opened = [c for c in gh.calls if "POST" in c][0]
        self.assertIn("title=Brain updates", opened)

    def test_land_reports_missing_approval(self):
        gh = LandGh(state="blocked")
        out = self.land(gh)
        self.assertFalse(out["merged"])
        self.assertIn("approval", out["missing"][0])
        self.assertIn("lead", out["missing"][0])
        self.assertEqual(gh.merges(), [])

    def test_land_reports_failed_and_pending_checks(self):
        gh = LandGh(checks=[("validate", "completed", "failure"), ("lint", "completed", "success")])
        out = self.land(gh)
        self.assertFalse(out["merged"])
        self.assertEqual(out["missing"], ["check validate failed"])
        self.assertEqual(gh.merges(), [])
        gh = LandGh(checks=[("validate", "in_progress", None)])
        out = self.land(gh, wait=30)
        self.assertFalse(out["merged"])
        self.assertIn("checks still running", out["missing"][0])
        self.assertIn("validate", out["missing"][0])
        self.assertEqual(self.sleeps, [15, 15])
        self.assertEqual(gh.merges(), [])

    def test_land_waits_for_checks_then_merges(self):
        gh = LandGh(checks=[("validate", "queued", None)])

        def sleep(seconds):
            gh.checks = [["validate", "completed", "success"]]
        with mock.patch("pb_core.repo.gh_json", gh), mock.patch("pb_core.merge.gh_json", gh):
            out = merge_land(self.repo, wait=600, sleep=sleep)
        self.assertTrue(out["merged"])

    def test_land_falls_back_to_squash_when_merge_commits_are_disabled(self):
        gh = LandGh(allow_merge_commit=False)
        out = self.land(gh)
        self.assertTrue(out["merged"])
        self.assertEqual(gh.merges(), [["merge_method=merge", "sha=abc123"], ["merge_method=squash", "sha=abc123"]])

    def test_land_with_nothing_to_merge(self):
        git(self.repo, "push", "-q", "-f", "origin", "main:refs/heads/docs/brain")
        gh = LandGh(open_prs=())
        out = self.land(gh)
        self.assertFalse(out["merged"])
        self.assertIn("nothing", out["problems"][0])
        self.assertFalse([c for c in gh.calls if "POST" in c])

    def test_land_never_pushes_to_the_default_branch(self):
        before = self.remote_sha("main")
        self.land(LandGh())
        self.assertEqual(self.remote_sha("main"), before)

    def test_land_cli_exit_codes(self):
        for gh, expected in ((LandGh(), 0), (LandGh(state="blocked"), 1)):
            with mock.patch("pb_core.repo.gh_json", gh), mock.patch("pb_core.merge.gh_json", gh):
                code, out, err = run_cli("merge", "land", "--wait", "0", cwd=self.repo)
            self.assertEqual(code, expected, (out, err))


if __name__ == "__main__":
    unittest.main()
