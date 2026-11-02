"""Regression tests for the final review findings."""
import os
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_brain, page, files_of, run_cli
from pb_core.secrets import scan
import test_gitops
from test_gitops import GIT_ENV, git


class CommitFixesTest(test_gitops.GitRepoCase):
    def test_commit_non_ascii_title(self):
        git(self.repo, "checkout", "-qb", "feat/q")
        rel, text = page("concept", "Qualità", "term_en: Quality")
        self.write("brain/" + rel, text)
        code, data, err = run_cli("commit", "-m", "m", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data["files"], ["brain/functional/concepts/Qualità.md"])
        self.assertEqual(git(self.repo, "status", "--porcelain", "brain"), "")

    def test_commit_rename_removes_old_path(self):
        git(self.repo, "checkout", "-qb", "feat/r")
        self.add_page("Invoice")
        run_cli("commit", "-m", "add", cwd=self.repo)
        git(self.repo, "mv", "brain/functional/features/Invoice.md", "brain/functional/features/Bill.md")
        code, data, err = run_cli("commit", "-m", "rename", cwd=self.repo)
        self.assertEqual(code, 0, err)
        tree = git(self.repo, "ls-tree", "-r", "--name-only", "HEAD", "brain/functional/features")
        self.assertEqual(tree.splitlines(), ["brain/functional/features/Bill.md"])
        self.assertEqual(git(self.repo, "status", "--porcelain", "brain"), "")
        self.assertIn("brain/functional/features/Invoice.md", data["files"])

    def test_commit_include_extra_paths(self):
        git(self.repo, "checkout", "-qb", "feat/i")
        self.write("CLAUDE.md", "pointer\n")
        self.write(".github/workflows/pb-validate.yml", "x\n")
        self.write("apps/other.ts", "x\n")
        code, data, err = run_cli("commit", "-m", "init", "--include", "CLAUDE.md", ".github/workflows/pb-validate.yml",
                                  cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(data["files"]), [".github/workflows/pb-validate.yml", "CLAUDE.md"])
        self.assertIn("?? apps/", git(self.repo, "status", "--porcelain"))

    def test_routine_discard_keeps_only_digest(self):
        run_cli("routine", "start", "--branch", "brain/inbox", cwd=self.repo)
        self.add_page("Invalid")
        self.write("brain/schema/brain.md", "changed\n")
        self.write("brain/digests/2026-10-31.md", "# Digest\n")
        code, data, err = run_cli("routine", "discard", cwd=self.repo)
        self.assertEqual(code, 0, err)
        status = git(self.repo, "status", "--porcelain", "--untracked-files=all", "brain")
        self.assertEqual(status, "?? brain/digests/2026-10-31.md")


class ScaffoldBranchTest(unittest.TestCase):
    def test_generate_workflow_targets_default_branch_not_current(self):
        saved = {k: os.environ.get(k) for k in GIT_ENV}
        os.environ.update(GIT_ENV)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                git(repo, "init", "-q", "-b", "main")
                (repo / "a.txt").write_text("x")
                git(repo, "add", "-A")
                git(repo, "commit", "-qm", "init")
                git(repo, "checkout", "-qb", "pb/init")
                code, data, _ = run_cli("scaffold", "--repo", repo, "--product", "P")
                self.assertEqual(code, 0)
                self.assertEqual(data["default_branch"], "main")
                self.assertIn('branches: ["main"]', (repo / ".github/workflows/pb-brain-branch.yml").read_text())
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class SecretsReviewTest(unittest.TestCase):
    def test_real_world_formats_caught(self):
        for text in ("DB_PASSWORD=hunter2hunter2", "STRIPE_API_KEY=Xk29fj3kLq0", "aws_secret_access_key = wJalrXUtnFEMI2K7MDENG",
                     '"password": "hunter2hunter2"', "sk_live_" + "a1B2c3D4e5F6g7H8i9J0", "sk-ant-api03-" + "x" * 30,
                     "AIza" + "B" * 35, "ASIAABCDEFGHIJKLMNOP", "DefaultEndpointsProtocol=https;AccountKey=" + "a" * 40,
                     "Authorization: Bearer " + "abc123def456ghi789jkl012"):
            with self.subTest(text=text):
                self.assertTrue(scan(text), text)

    def test_prose_not_blocked(self):
        for text in ("password: required", "Pwd: unchanged", "Password: Argon2id-hashed",
                     "The client_secret: configurable per tenant", "postgres://app:${DB_PASS}@db",
                     "postgres://app:<password>@db"):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [], text)


class TemplatesTest(unittest.TestCase):
    def test_validate_uses_base_toolkit_and_never_automerges_toolkit(self):
        text = (ROOT / "templates/github/pb-validate.yml").read_text()
        self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", text)
        self.assertIn("--brain brain validate", text)
        self.assertIn("brain/.pb/toolkit/", text)

    def test_routine_prompt_uses_defined_pb_only(self):
        text = (ROOT / "templates/routine/prompt.md").read_text()
        self.assertIn('PB="python3 brain/.pb/toolkit/pb.py"', text)
        for line in text.splitlines():
            self.assertNotRegex(line, r"`pb (validate|routine)")
        self.assertIn("$PB routine discard", text)

    def test_routine_prompt_needs_no_plugin(self):
        text = (ROOT / "templates/routine/prompt.md").read_text()
        self.assertNotIn("Run `/pb:", text)
        self.assertIn("brain/.pb/toolkit/skills/sync/SKILL.md", text)
        self.assertIn("`BASE` is `brain/.pb/toolkit/skills/sync`", text)


class AliasStringTest(unittest.TestCase):
    def test_single_string_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp, files_of(
                page("concept", "Invoice", "term_en: Invoice\naliases: Fattura", "[[Payment]]"),
                page("concept", "Payment", "term_en: Payment\naliases: Pagamento", "[[Invoice]]"),
            ))
            _, data, _ = run_cli("resolve", "o", cwd=repo)
            self.assertNotIn("alias", [c["match"] for c in data["candidates"]])
            _, data, _ = run_cli("resolve", "fattura", cwd=repo)
            self.assertEqual(data["candidates"][0]["match"], "alias")
            _, data, _ = run_cli("lint", cwd=repo)
            self.assertNotIn("duplicate-candidate", {f["code"] for f in data["findings"]})


if __name__ == "__main__":
    unittest.main()
