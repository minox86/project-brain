"""The plugin adapts to the repo's commit rules: detection, format, composition, rejection by a hook."""
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, run_cli
from pb_core.brain import Brain
from pb_core.errors import UsageError
from pb_core.messages import commit_message, pr_title
from test_gitops import BrainBranchCase, GitRepoCase, git
from test_merge import MergeCase

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
HOOK = """#!/bin/sh
if ! head -1 "$1" | grep -Eq '^(feat|fix|docs|chore)(\\(.+\\))?: '; then
  echo "commit-msg: subject must follow the conventional format" >&2
  exit 1
fi
"""


def touch(root, rel, text="x"):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def set_setting(repo, key, value):
    """Replace one setting of brain/.pb/schema/brain.md."""
    path = Path(repo) / "brain/.pb/schema/brain.md"
    lines = [f"{key}: {json.dumps(value)}" if line.startswith(f"{key}:") else line
             for line in path.read_text().splitlines()]
    path.write_text("\n".join(lines) + "\n")


def set_format(repo, fmt):
    set_setting(repo, "commit_format", fmt)


def install_hook(repo):
    hook = Path(repo) / ".git/hooks/commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class ScanCommitRulesTest(unittest.TestCase):
    def test_no_rules_gives_four_empty_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            touch(tmp, "package.json", '{"name": "x"}')
            touch(tmp, ".github/workflows/ci.yml", "jobs: {}")
            touch(tmp, "lefthook.yml", "pre-commit: {}")
            code, data, err = run_cli("scan", "--repo", tmp)
            self.assertEqual(code, 0, err)
            self.assertEqual(data["commit_rules"],
                             {"commitlint": [], "hooks": [], "pr_checks": [], "recent_subjects": []})

    def test_each_signal_is_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            touch(tmp, "commitlint.config.js", "module.exports = {}")
            touch(tmp, ".commitlintrc.yml", "extends: []")
            touch(tmp, "package.json", '{"name": "x", "commitlint": {"extends": []}}')
            touch(tmp, "apps/web/commitlint.config.js")  # not at the root
            touch(tmp, ".husky/commit-msg", "npx commitlint --edit")
            touch(tmp, "lefthook.yml", "commit-msg:\n  commands: {}")
            touch(tmp, ".pre-commit-config.yaml", "repos:\n- repo: conventional-pre-commit")
            touch(tmp, ".gitlint", "[general]")
            touch(tmp, ".github/workflows/pr.yml", "uses: amannn/action-semantic-pull-request@v5")
            touch(tmp, ".github/workflows/lint.yaml", "run: npx commitlint --from origin/main")
            touch(tmp, ".github/workflows/ci.yml", "run: make test")
            code, data, err = run_cli("scan", "--repo", tmp)
            self.assertEqual(code, 0, err)
            rules = data["commit_rules"]
            self.assertEqual(rules["commitlint"], [".commitlintrc.yml", "commitlint.config.js", "package.json"])
            self.assertEqual(rules["hooks"], [".gitlint", ".husky/commit-msg", ".pre-commit-config.yaml",
                                              "lefthook.yml"])
            self.assertEqual(rules["pr_checks"], [".github/workflows/lint.yaml", ".github/workflows/pr.yml"])

    def test_recent_subjects_of_the_default_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            git(tmp, "init", "-q", "-b", "main")
            for i in range(17):
                touch(tmp, "f.txt", str(i))
                git(tmp, "add", "-A")
                git(tmp, "commit", "-qm", f"feat: change {i}")
            code, data, err = run_cli("scan", "--repo", tmp)
            self.assertEqual(code, 0, err)
            subjects = data["commit_rules"]["recent_subjects"]
            self.assertEqual(len(subjects), 15)
            self.assertEqual(subjects[0], "feat: change 16")


class MessagesTest(unittest.TestCase):
    def brain(self, fmt=None, **settings):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = make_brain(tmp.name)
        if fmt is not None:
            set_format(repo, fmt)
        for key, value in settings.items():
            set_setting(repo, key, value)
        return Brain(repo / "brain"), repo

    def test_default_format(self):
        brain, _ = self.brain()
        self.assertEqual(commit_message(brain, "put", "add X"), "pb(put): add X")

    def test_configured_format(self):
        brain, _ = self.brain("docs(brain): {summary}")
        self.assertEqual(commit_message(brain, "put", "add X"), "docs(brain): add X")

    def test_summary_is_one_line_and_not_empty(self):
        brain, _ = self.brain()
        self.assertEqual(commit_message(brain, "put", "  add X\n\n  and Y  "), "pb(put): add X and Y")
        for blank in ("", "  \n "):
            with self.assertRaises(UsageError):
                commit_message(brain, "put", blank)

    def test_pr_titles(self):
        brain, _ = self.brain()
        self.assertEqual(pr_title(brain, "brain"), "Brain updates")
        self.assertEqual(pr_title(brain, "init"), "Create the project brain")
        brain, _ = self.brain(pr_title_brain="docs: brain updates")
        self.assertEqual(pr_title(brain, "brain"), "docs: brain updates")
        with self.assertRaises(UsageError):
            pr_title(brain, "other")

    def test_bad_commit_format_is_a_validation_error(self):
        for fmt in ("docs: brain", "{skill}: {summary} {ticket}"):
            with self.subTest(fmt=fmt):
                _, repo = self.brain(fmt)
                code, data, _ = run_cli("validate", cwd=repo)
                self.assertEqual(code, 1, data)
                self.assertIn((".pb/schema/brain.md", "bad-commit-format"),
                              [(e["path"], e["code"]) for e in data["errors"]])
                code, data, _ = run_cli("lint", cwd=repo)
                self.assertIn("bad-commit-format", [f["code"] for f in data["findings"]])

    def test_the_four_settings_validate(self):
        _, repo = self.brain("docs(brain): {summary}", pr_title_brain="Docs", pr_title_init="docs: brain",
                             commit_rules="max 72 chars")
        code, data, _ = run_cli("validate", cwd=repo)
        self.assertEqual(code, 0, data)

    def test_message_command(self):
        _, repo = self.brain("docs(brain): {summary}")
        code, data, err = run_cli("message", "--skill", "init", "-m", "create brain", cwd=repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"message": "docs(brain): create brain", "pr_title_brain": "Brain updates",
                                "pr_title_init": "Create the project brain",
                                "commit_format": "docs(brain): {summary}", "commit_rules": None})


class CommitFormatTest(GitRepoCase):
    def subject(self):
        return git(self.repo, "log", "-1", "--format=%s")

    def test_commit_composes_the_subject(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        self.add_page("Approval")
        code, data, err = run_cli("commit", "--skill", "put", "-m", "add X", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertIsNone(data["rejected"])
        self.assertEqual(self.subject(), "pb(put): add X")

    def test_raw_commits_verbatim(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        self.add_page("Approval")
        code, data, err = run_cli("commit", "--raw", "-m", "docs(brain): add X", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.subject(), "docs(brain): add X")

    def test_rejected_commit_keeps_everything_and_retry_with_raw(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        install_hook(self.repo)
        head = git(self.repo, "rev-parse", "HEAD")
        self.add_page("Approval")
        code, data, err = run_cli("commit", "--skill", "put", "-m", "add X", cwd=self.repo)
        self.assertEqual(code, 1, (data, err))
        self.assertFalse(data["committed"])
        self.assertEqual(data["rejected"]["message"], "pb(put): add X")
        self.assertIn("conventional format", data["rejected"]["output"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertIn("brain/functional/features/Approval.md", git(self.repo, "status", "--porcelain"))
        code, data, err = run_cli("commit", "--raw", "-m", "docs(brain): add X", cwd=self.repo)
        self.assertEqual(code, 0, (data, err))
        self.assertTrue(data["committed"])
        self.assertEqual(self.subject(), "docs(brain): add X")

    def test_configured_format_satisfies_the_hook(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        install_hook(self.repo)
        set_format(self.repo, "docs(brain): {summary}")
        self.add_page("Approval")
        code, data, err = run_cli("commit", "--skill", "put", "-m", "add X", cwd=self.repo)
        self.assertEqual(code, 0, (data, err))
        self.assertEqual(self.subject(), "docs(brain): add X")


class RoutineRejectedTest(BrainBranchCase):
    def test_routine_finish_rejected_pushes_nothing(self):
        git(self.repo, "push", "-q", "origin", "main:refs/heads/docs/brain")
        before = git(self.remote, "rev-parse", "docs/brain")
        install_hook(self.repo)
        self.start()
        self.add_page("Approval")
        code, data, err = run_cli("routine", "finish", "--branch", "docs/brain", "-m", "sync", cwd=self.repo)
        self.assertEqual(code, 1, (data, err))
        self.assertEqual((data["committed"], data["pushed"], data["conflict"]), (False, False, False))
        self.assertEqual(data["rejected"]["message"], "pb(routine): sync")
        self.assertIn("conventional format", data["rejected"]["output"])
        self.assertIn("the commit was rejected by the repo's commit rules", data["problems"])
        self.assertEqual(git(self.remote, "rev-parse", "docs/brain"), before)
        self.assertEqual(self.gh.calls, [])

    def test_brain_pr_uses_the_configured_title(self):
        set_setting(self.repo, "pr_title_brain", "docs: brain updates")
        self.commit_all("title", "main")
        self.start()
        self.add_page("Approval")
        data = self.finish()
        self.assertIsNone(data["rejected"])
        self.assertIn("title=docs: brain updates", self.gh.fields("open"))


class MergeRejectedTest(MergeCase):
    def test_merge_finish_rejected_then_raw_retry(self):
        def routine():
            self.put("decision", "R", "area: technical\nsources: [\"jira:FIN-1\"]")
        self.on_brain_branch(routine)
        self.on_main(lambda: self.put("concept", "D", "term_en: D\nsources: [\"jira:FIN-1\"]"))
        install_hook(self.repo)
        code, out, err = run_cli("merge", "start", "--worktree", self.worktree, cwd=self.repo)
        self.assertEqual(code, 0, (out, err))
        before = self.remote_sha("docs/brain")
        code, out, err = run_cli("merge", "finish", "--worktree", self.worktree, "-m", "bring main",
                                 cwd=self.repo)
        self.assertEqual(code, 1, (out, err))
        self.assertEqual((out["committed"], out["pushed"]), (False, False))
        self.assertEqual(out["rejected"]["message"], "pb(merge): bring main")
        self.assertEqual(self.remote_sha("docs/brain"), before)
        self.assertEqual(subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=self.worktree,
                                        capture_output=True).returncode, 0)
        code, out, err = run_cli("merge", "finish", "--worktree", self.worktree, "--raw",
                                 "-m", "chore(brain): bring main into docs/brain", cwd=self.repo)
        self.assertEqual(code, 0, (out, err))
        self.assertEqual((out["committed"], out["pushed"]), (True, True))
        self.assertIsNone(out["rejected"])
        self.assertEqual(git(self.remote, "log", "-1", "--format=%s", "docs/brain"),
                         "chore(brain): bring main into docs/brain")
        self.assertEqual(len(git(self.remote, "log", "-1", "--format=%p", "docs/brain").split()), 2)


class NeverBypassTest(unittest.TestCase):
    def test_no_hook_bypass_in_scripts(self):
        found = []
        for path in SCRIPTS.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in ("--no-verify", "core.hooksPath", "HUSKY=0", '"-n"', "'-n'"):
                if banned in text:
                    found.append(f"{path.relative_to(SCRIPTS)}: {banned}")
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
