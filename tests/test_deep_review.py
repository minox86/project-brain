"""Findings of the deep review of the toolkit, each reproduced before its fix."""
import tempfile
import unittest
from pathlib import Path

from helpers import page, run_cli
from test_gitops import GitRepoCase, git


class ValidateFindingsTest(GitRepoCase):
    def test_validate_takes_brain_prefixed_paths(self):
        rel, text = page("concept", "Broken", "term_en: [unclosed")
        self.write("brain/" + rel, text)
        code, data, _ = run_cli("validate", "brain/" + rel, cwd=self.repo)
        self.assertEqual(code, 1)
        code, data, _ = run_cli("validate", "brain/functional/concepts/Nope.md", cwd=self.repo)
        self.assertEqual(data["errors"][0]["code"], "unknown-path")


class RoutineStartTest(GitRepoCase):
    def test_routine_start_needs_no_brain_in_the_checkout(self):
        git(self.repo, "push", "-q", "origin", "main:refs/heads/docs/brain")
        git(self.repo, "rm", "-rq", "brain")
        git(self.repo, "commit", "-qm", "no brain here")
        with tempfile.TemporaryDirectory() as tmp:
            code, data, err = run_cli("routine", "start", "--branch", "docs/brain", "--worktree",
                                      Path(tmp) / "wt", cwd=self.repo)
            self.assertEqual(code, 0, err)
            self.assertTrue(Path(data["brain"]).is_dir())
            run_cli("routine", "cleanup", "--worktree", Path(tmp) / "wt", cwd=self.repo)

    def test_include_of_a_missing_file_is_skipped(self):
        self.add_page("Approval")
        git(self.repo, "switch", "-qc", "work")
        code, data, err = run_cli("commit", "-m", "x", "--include", ".github/workflows/pb-generate.yml",
                                  cwd=self.repo)
        self.assertEqual(code, 0, err)


class TextFindingsTest(unittest.TestCase):
    def test_non_ascii_names_resolve(self):
        from pb_core.resolve import _norm
        self.assertNotEqual(_norm("Пример"), _norm("日本語"))
        self.assertEqual(_norm("Città"), _norm("citta"))

    def test_escaped_quotes_in_frontmatter(self):
        from pb_core.frontmatter import parse
        meta, _ = parse('---\ntitle: "say \\"hi\\" # now"\n---\n')
        self.assertEqual(meta["title"], 'say "hi" # now')

    def test_product_with_hash_keeps_its_name(self):
        from pb_core.scaffold import NEEDS_QUOTES
        self.assertTrue(NEEDS_QUOTES.search("Team #1"))


if __name__ == "__main__":
    unittest.main()
