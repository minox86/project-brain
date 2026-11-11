import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import make_brain, page, run_cli
from pb_core.gitops import adds_nothing
from test_brain_pr import FakeGh

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def git(cwd, *args):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True, check=True).stdout.strip()


class GitRepoCase(unittest.TestCase):
    review_policy = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._env = {k: os.environ.get(k) for k in GIT_ENV}
        os.environ.update(GIT_ENV)
        self.addCleanup(self._restore_env)
        base = Path(self.tmp.name)
        self.remote = base / "remote.git"
        git(base, "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.repo = make_brain(base / "repo")
        if not self.review_policy:
            (self.repo / "brain/schema/review.md").unlink()  # no policy: every change goes straight to the branch
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "remote", "set-head", "origin", "main")

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write(self, rel, text="x\n", root=None):
        path = (root or self.repo) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def add_page(self, title, root=None):
        rel, text = page("feature", title)
        self.write("brain/" + rel, text, root)


class GitopsTest(GitRepoCase):
    def test_commit_only_brain_and_carries_generated_files(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        self.add_page("Approval")
        self.write("brain/index.md", "generated\n")
        self.write("apps/web/a.ts", "code\n")
        git(self.repo, "add", "apps/web/a.ts")
        code, data, err = run_cli("commit", "--skill", "put", "-m", "add approval", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertTrue(data["committed"])
        self.assertEqual(data["branch"], "feat/x")
        expected = ["brain/functional/features/Approval.md", "brain/index.md"]
        self.assertEqual(sorted(data["files"]), expected)
        shown = git(self.repo, "show", "--name-only", "--format=%s", "HEAD").splitlines()
        self.assertEqual(shown[0], "pb(put): add approval")
        self.assertEqual(sorted(l for l in shown[1:] if l), expected)
        self.assertIn("A  apps/web/a.ts", git(self.repo, "status", "--porcelain"))

    def test_commit_refuses_default_branch(self):
        self.add_page("Approval")
        code, data, _ = run_cli("commit", "-m", "m", cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "on-default-branch")
        self.assertEqual(data["branch"], "main")
        code, data, _ = run_cli("commit", "-m", "m", "--allow-default", cwd=self.repo)
        self.assertEqual(code, 0)
        self.assertTrue(data["committed"])

    def test_commit_nothing_to_commit(self):
        git(self.repo, "checkout", "-qb", "feat/y")
        code, data, _ = run_cli("commit", "-m", "m", cwd=self.repo)
        self.assertEqual(code, 0)
        self.assertFalse(data["committed"])

    def test_routine_start_creates_missing_branch(self):
        code, data, err = run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"branch": "docs/brain", "created": True, "restarted": False, "behind": 0})
        self.assertEqual(git(self.repo, "branch", "--show-current"), "docs/brain")

    def test_routine_finish_pushes(self):
        run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)
        self.add_page("Approval")
        code, data, err = run_cli("routine", "finish", "--branch", "docs/brain", "-m", "sync", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"committed": True, "pushed": True, "conflict": False, "pr": None, "watched": [],
                                "reviewers": NO_REVIEWERS, "behind": 0,
                                "retention": {"archived": [], "deleted": []}, "rejected": None, "problems": [
                                    "no GitHub repo (github.repo in sources.md): the brain PR from "
                                    "docs/brain to main was not opened"]})
        log = git(self.remote, "log", "--format=%s", "docs/brain")
        self.assertEqual(log.splitlines()[:2], ["pb(routine): sync", "init"])
        shown = git(self.remote, "show", "--name-only", "--format=", "docs/brain").splitlines()
        self.assertIn("brain/functional/features/Approval.md", shown)
        self.assertIn("brain/index.md", shown)  # one commit carries pages and generated files
        self.assertEqual(git(self.repo, "status", "--porcelain", "--", "brain"), "")
        code, data, _ = run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)
        self.assertFalse(data["created"])

    def test_routine_finish_refuses_the_default_branch(self):
        run_cli("routine", "start", "--branch", "main", cwd=self.repo)
        self.add_page("Approval")
        before = git(self.remote, "rev-parse", "main")
        code, data, _ = run_cli("routine", "finish", "--branch", "main", "-m", "sync", cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("default branch", data["error"])
        self.assertEqual(git(self.remote, "rev-parse", "main"), before)


NO_REVIEWERS = {"areas": [], "handles": [], "users": [], "teams": []}


class RoutineGuardTest(GitRepoCase):
    """The routine commands never act on a developer's checkout and never push anywhere but docs/brain."""

    def developer_at_work(self):
        git(self.repo, "push", "-q", "origin", "main:refs/heads/docs/brain")
        git(self.repo, "checkout", "-qb", "feat/x")
        self.write("apps/web/a.ts", "code\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "code")
        self.add_page("Draft")
        self.write("apps/web/b.ts", "staged\n")
        git(self.repo, "add", "apps/web/b.ts")
        return self.snapshot()

    def snapshot(self):
        return {"head": git(self.repo, "rev-parse", "HEAD"), "branch": git(self.repo, "branch", "--show-current"),
                "status": git(self.repo, "status", "--porcelain", "--untracked-files=all"),
                "index": git(self.repo, "diff", "--cached"),
                "remote": git(self.remote, "for-each-ref", "--format=%(refname) %(objectname)")}

    def test_finish_refuses_on_a_working_branch(self):
        before = self.developer_at_work()
        code, data, _ = run_cli("routine", "finish", "--branch", "docs/brain", "-m", "sync",
                                cwd=self.repo)
        self.assertEqual(code, 2, data)
        self.assertIn("feat/x", data["error"])
        self.assertEqual(self.snapshot(), before)

    def test_discard_refuses_on_a_working_branch(self):
        before = self.developer_at_work()
        code, data, _ = run_cli("routine", "discard", cwd=self.repo)
        self.assertEqual(code, 2, data)
        self.assertIn("feat/x", data["error"])
        self.assertEqual(self.snapshot(), before)
        self.assertTrue((self.repo / "brain/functional/features/Draft.md").is_file())

    def test_start_and_finish_reject_another_branch(self):
        before = self.snapshot()
        code, data, _ = run_cli("routine", "start", "--branch", "brain/inbox", cwd=self.repo)
        self.assertEqual(code, 2, data)
        self.assertIn("docs/brain", data["error"])
        wt = Path(self.tmp.name) / "run"
        code, data, _ = run_cli("routine", "start", "--branch", "brain/inbox", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 2, data)
        self.assertFalse(wt.exists())
        self.assertEqual(self.snapshot(), before)
        run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)
        self.add_page("Approval")
        code, data, _ = run_cli("routine", "finish", "--branch", "brain/inbox", "-m", "m", cwd=self.repo)
        self.assertEqual(code, 2, data)
        self.assertIn("docs/brain", data["error"])
        self.assertEqual(git(self.remote, "for-each-ref", "--format=%(refname)"), "refs/heads/main")


class BrainBranchCase(GitRepoCase):
    """The routine on docs/brain, GitHub replaced by a FakeGh."""

    def setUp(self):
        super().setUp()
        self.write("brain/schema/sources.md", "---\ngithub: {repo: o/r}\n---\n# Sources\n")
        git(self.repo, "commit", "-qam", "sources")
        git(self.repo, "push", "-q", "origin", "main")
        self.gh = FakeGh()
        patcher = mock.patch("pb_core.repo.gh_json", self.gh)
        patcher.start()
        self.addCleanup(patcher.stop)

    def commit_all(self, message, branch):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", message)
        git(self.repo, "push", "-q", "origin", branch)

    def brain_branch_with_page(self, title="Approval"):
        """docs/brain on origin with one page main lacks; the checkout back on main."""
        git(self.repo, "checkout", "-qb", "docs/brain")
        self.add_page(title)
        self.commit_all(f"add {title}", "docs/brain")
        git(self.repo, "checkout", "-q", "main")

    def main_moves_on(self, n=2):
        for i in range(n):
            self.write(f"apps/web/f{i}.ts", f"code {i}\n")
            self.commit_all(f"code {i}", "main")

    def squash_merge(self, title="Approval"):
        """main gets the page of docs/brain as a different commit, as a squash merge does."""
        self.add_page(title)
        self.commit_all("Brain updates (#1)", "main")

    def start(self):
        code, data, err = run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)
        self.assertEqual(code, 0, err)
        return data

    def finish(self, *extra, expect=0):
        code, data, err = run_cli("routine", "finish", "--branch", "docs/brain", "-m", "sync",
                                  *extra, cwd=self.repo)
        self.assertEqual(code, expect, (data, err))
        return data


class RoutineStartTest(BrainBranchCase):
    def test_start_restarts_branch_when_its_pr_was_squash_merged(self):
        self.brain_branch_with_page()
        self.squash_merge()
        self.main_moves_on(1)
        out = self.start()
        self.assertTrue(out["restarted"])
        self.assertEqual(out["behind"], 0)
        self.assertFalse(out["created"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/main"))
        self.assertEqual(git(self.repo, "branch", "--show-current"), "docs/brain")

    def test_start_keeps_branch_with_pending_pages_and_reports_behind(self):
        self.brain_branch_with_page()
        self.main_moves_on(2)
        out = self.start()
        self.assertFalse(out["restarted"])
        self.assertEqual(out["behind"], 2)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/docs/brain"))
        self.assertEqual(git(self.repo, "rev-list", "--merges", "--count", "HEAD"), "0")

    def test_start_in_worktree_restarts_too(self):
        self.brain_branch_with_page()
        self.squash_merge()
        wt = Path(self.tmp.name) / "run"
        code, out, err = run_cli("routine", "start", "--branch", "docs/brain", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual((out["restarted"], out["behind"]), (True, 0))
        self.assertEqual(git(wt, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/main"))
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")

    def test_start_in_worktree_reports_behind(self):
        self.brain_branch_with_page()
        self.main_moves_on(2)
        wt = Path(self.tmp.name) / "run"
        code, out, err = run_cli("routine", "start", "--branch", "docs/brain", "--worktree", wt, cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual((out["restarted"], out["behind"]), (False, 2))
        self.assertEqual(git(wt, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/docs/brain"))

    def test_adds_nothing(self):
        self.brain_branch_with_page()
        git(self.repo, "fetch", "-q", "origin")
        self.assertFalse(adds_nothing(self.repo, "docs/brain", "main"))
        self.squash_merge()
        git(self.repo, "fetch", "-q", "origin")
        self.assertTrue(adds_nothing(self.repo, "docs/brain", "main"))
        self.assertFalse(adds_nothing(self.repo, "no/such-branch", "main"))

    def test_adds_nothing_is_false_on_conflict(self):
        self.brain_branch_with_page()
        rel, text = page("feature", "Approval")
        self.write("brain/" + rel, text.replace("Body.", "Other body."))
        self.commit_all("theirs", "main")
        git(self.repo, "fetch", "-q", "origin")
        self.assertFalse(adds_nothing(self.repo, "docs/brain", "main"))


class RoutineFinishTest(BrainBranchCase):
    review_policy = True

    def test_finish_pushes_everything_in_one_branch_no_review_branch(self):
        self.start()
        rel, text = page("decision", "X")
        self.write("brain/" + rel, text)
        out = self.finish()
        self.assertTrue(out["pushed"])
        self.assertEqual(out["watched"][0]["path"], "decisions/X.md")
        self.assertNotIn("review", out)
        self.assertNotIn("promotion", out)
        self.assertEqual(git(self.repo, "ls-remote", "--heads", "origin", "pb/review/*"), "")
        self.assertIn("brain/decisions/X.md",
                      git(self.repo, "ls-tree", "-r", "--name-only", "origin/docs/brain").splitlines())
        self.assertEqual(out["pr"], "https://github.com/o/r/pull/7")
        self.assertEqual(self.gh.fields("open")[:3], ["title=Brain updates", "head=docs/brain", "base=main"])
        self.assertIn("decisions/X.md", self.gh.fields("open")[3])

    def test_finish_body_keeps_watched_changes_of_earlier_runs(self):
        self.start()
        rel, text = page("decision", "X")
        self.write("brain/" + rel, text)
        self.finish()
        self.gh.open_prs = [{"number": 7, "html_url": "https://github.com/o/r/pull/7"}]
        self.start()
        self.add_page("Unwatched")
        out = self.finish()
        self.assertIn("decisions/X.md", [w["path"] for w in out["watched"]])
        self.assertIn("decisions/X.md", self.gh.fields("patch")[-1])
        self.assertNotIn("nothing on a watched point", self.gh.fields("patch")[-1])

    def test_finish_low_confidence_page_is_watched(self):
        self.start()
        self.add_page("Approval")
        out = self.finish("--confidence", "brain/functional/features/Approval.md=low")
        watched = {w["path"]: w["reasons"] for w in out["watched"]}
        self.assertIn("confidence: low", watched["functional/features/Approval.md"])
        self.assertIn("functional/features/Approval.md", self.gh.fields("open")[3])

    def test_finish_updates_open_pr_and_requests_reviewers(self):
        self.write("brain/schema/review.md",
                   '---\nreviewers: {technical: ["acme/backend"], functional: [pm]}\n'
                   "watch: [{type: decision}]\n---\n# Review policy\n")
        self.commit_all("policy", "main")
        self.gh.open_prs = [{"number": 12, "html_url": "https://github.com/o/r/pull/12"}]
        self.start()
        rel, text = page("decision", "X")
        self.write("brain/" + rel, text)
        out = self.finish()
        self.assertEqual(out["pr"], "https://github.com/o/r/pull/12")
        self.assertIsNone(self.gh.fields("open"))
        self.assertIn("decisions/X.md", self.gh.fields("patch")[-1])
        self.assertEqual(sorted(self.gh.fields("reviewers")), ["reviewers[]=pm", "team_reviewers[]=backend"])
        self.assertEqual(out["reviewers"]["users"], ["pm"])
        self.assertEqual(out["problems"], [])

    def test_finish_never_requests_the_pr_author(self):
        self.write("brain/schema/review.md",
                   '---\nreviewers: {functional: [owner]}\nwatch: [{type: decision}]\n---\n# Review policy\n')
        self.commit_all("policy", "main")
        self.gh.open_prs = [{"number": 12, "html_url": "https://github.com/o/r/pull/12", "user": {"login": "owner"}}]
        self.start()
        rel, text = page("decision", "X", "area: functional")
        self.write("brain/" + rel, text)
        out = self.finish()
        self.assertEqual(out["reviewers"]["users"], ["owner"])
        self.assertIsNone(self.gh.fields("reviewers"))
        self.assertEqual(out["problems"], [])

    def test_finish_on_behind_branch_reports_behind(self):
        self.brain_branch_with_page()
        self.main_moves_on(2)
        self.start()
        self.add_page("Second")
        out = self.finish()
        self.assertTrue(out["pushed"])
        self.assertEqual(out["behind"], 2)
        self.assertIn("`docs/brain` is behind `main`: run `/pb:merge`", self.gh.fields("open")[3])
        self.assertEqual(git(self.repo, "rev-list", "--merges", "--count", "origin/docs/brain"), "0")

    def test_finish_after_restart_pushes_over_the_old_branch(self):
        self.brain_branch_with_page()
        self.squash_merge()
        self.main_moves_on(1)
        old = git(self.repo, "rev-parse", "origin/docs/brain")
        self.assertTrue(self.start()["restarted"])
        self.add_page("Second")
        out = self.finish()
        self.assertTrue(out["pushed"])
        self.assertFalse(out["conflict"])
        self.assertEqual(git(self.remote, "rev-parse", "docs/brain"), git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(git(self.repo, "rev-parse", "HEAD~1"), git(self.repo, "rev-parse", "origin/main"))
        self.assertNotEqual(subprocess.run(["git", "merge-base", "--is-ancestor", old, "HEAD"],
                                           cwd=str(self.repo)).returncode, 0)

    def test_finish_refused_push_reports_conflict(self):
        self.brain_branch_with_page()
        self.start()
        other = Path(self.tmp.name) / "other"
        git(Path(self.tmp.name), "clone", "-q", "-b", "docs/brain", str(self.remote), str(other))
        self.add_page("Theirs", root=other)
        git(other, "add", "-A")
        git(other, "commit", "-qm", "theirs")
        git(other, "push", "-q", "origin", "docs/brain")
        self.add_page("Ours")
        out = self.finish(expect=1)
        self.assertEqual((out["conflict"], out["pushed"], out["pr"]), (True, False, None))
        self.assertEqual(git(self.remote, "log", "--format=%s", "-1", "docs/brain"), "theirs")
        self.assertEqual(self.gh.calls, [])

    def test_finish_push_rejected_by_remote_leaves_branch(self):
        self.brain_branch_with_page()
        before = git(self.remote, "rev-parse", "docs/brain")
        self.start()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.add_page("Ours")
        out = self.finish(expect=1)
        self.assertEqual((out["conflict"], out["pushed"]), (True, False))
        self.assertIn("the push to docs/brain was refused", out["problems"])
        self.assertEqual(git(self.remote, "rev-parse", "docs/brain"), before)

    def test_finish_runs_retention(self):
        self.write("brain/digests/2020-01-01.md", "# Old digest\n")
        self.commit_all("old digest", "main")
        self.start()
        out = self.finish()
        self.assertEqual(out["retention"]["deleted"], ["digests/2020-01-01.md"])
        self.assertNotIn("brain/digests/2020-01-01.md",
                         git(self.repo, "ls-tree", "-r", "--name-only", "origin/docs/brain").splitlines())

    def test_run_after_github_deleted_docs_brain(self):
        self.start()
        self.add_page("Approval")
        self.assertTrue(self.finish()["pushed"])
        git(self.remote, "branch", "-D", "docs/brain")  # squash-merged, head branch deleted by GitHub
        out = self.start()
        self.assertEqual((out["created"], out["restarted"]), (True, False))
        self.add_page("Second")
        out = self.finish()
        self.assertEqual((out["pushed"], out["conflict"]), (True, False))
        self.assertEqual(git(self.remote, "rev-parse", "docs/brain"), git(self.repo, "rev-parse", "HEAD"))

    def test_finish_with_nothing_ahead_opens_no_pr(self):
        run_cli("generate", cwd=self.repo)
        self.commit_all("generated", "main")
        self.start()
        out = self.finish()
        self.assertEqual((out["pushed"], out["pr"], out["problems"]), (True, None, []))
        self.assertEqual(self.gh.calls, [])

if __name__ == "__main__":
    unittest.main()
