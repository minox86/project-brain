import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, page, run_cli

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def git(cwd, *args):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True, check=True).stdout.strip()


class GitRepoCase(unittest.TestCase):
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
    def test_commit_only_brain_and_excludes_generated(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        self.add_page("Approval")
        self.write("brain/index.md", "generated\n")
        self.write("apps/web/a.ts", "code\n")
        git(self.repo, "add", "apps/web/a.ts")
        code, data, err = run_cli("commit", "-m", "pb(put): add approval", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertTrue(data["committed"])
        self.assertEqual(data["branch"], "feat/x")
        self.assertEqual(data["files"], ["brain/functional/features/Approval.md"])
        shown = git(self.repo, "show", "--name-only", "--format=%s", "HEAD").splitlines()
        self.assertEqual(shown[0], "pb(put): add approval")
        self.assertEqual([l for l in shown[1:] if l], ["brain/functional/features/Approval.md"])
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
        code, data, err = run_cli("routine", "start", "--branch", "brain/inbox", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"branch": "brain/inbox", "created": True})
        self.assertEqual(git(self.repo, "branch", "--show-current"), "brain/inbox")

    def test_routine_finish_pushes(self):
        run_cli("routine", "start", "--branch", "brain/inbox", cwd=self.repo)
        self.add_page("Approval")
        code, data, err = run_cli("routine", "finish", "--branch", "brain/inbox", "-m", "pb(routine): sync", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"committed": True, "pushed": True, "conflict": False})
        log = git(self.remote, "log", "--format=%s", "brain/inbox")
        self.assertEqual(log.splitlines()[0], "pb(routine): sync")
        code, data, _ = run_cli("routine", "start", "--branch", "brain/inbox", cwd=self.repo)
        self.assertFalse(data["created"])

    def test_routine_finish_to_main(self):
        run_cli("routine", "start", "--branch", "main", cwd=self.repo)
        self.add_page("Approval")
        code, data, _ = run_cli("routine", "finish", "--branch", "main", "-m", "pb(routine): sync", cwd=self.repo)
        self.assertEqual((code, data["pushed"]), (0, True))

    def test_routine_finish_conflict_aborts_without_push(self):
        other = Path(self.tmp.name) / "other"
        git(Path(self.tmp.name), "clone", "-q", str(self.remote), str(other))
        self.add_page("Approval", root=other)
        self.write("brain/functional/features/Approval.md", "---\ntype: feature\ntitle: Approval\n---\nTheirs.\n", other)
        git(other, "add", "-A")
        git(other, "commit", "-qm", "theirs")
        git(other, "push", "-q", "origin", "main")
        run_cli("routine", "start", "--branch", "main", cwd=self.repo)
        git(self.repo, "reset", "-q", "--hard", "HEAD~0")
        git(self.repo, "reset", "-q", "--hard", git(self.repo, "rev-list", "--max-parents=0", "HEAD"))
        self.write("brain/functional/features/Approval.md", "---\ntype: feature\ntitle: Approval\n---\nOurs.\n")
        code, data, _ = run_cli("routine", "finish", "--branch", "main", "-m", "ours", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertEqual(data, {"committed": True, "pushed": False, "conflict": True})
        self.assertEqual(git(self.remote, "log", "--format=%s", "-1", "main"), "theirs")
        self.assertFalse((self.repo / ".git" / "rebase-merge").exists())


if __name__ == "__main__":
    unittest.main()
