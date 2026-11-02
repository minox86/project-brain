"""Findings of the deep review of the toolkit, each reproduced before its fix."""
import tempfile
import unittest
from pathlib import Path

from helpers import page, run_cli
from test_gitops import GitRepoCase, git
from test_workspace import SRC, WorkspaceCase


class SaveFindingsTest(WorkspaceCase):
    def test_multiline_message_still_holds_watched_pages(self):
        decision = self.put("decision", "Single approver", f"area: technical\n{SRC}")
        code, data, err = run_cli("save", "-m", "pb(put): x\n\nDetails", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn(decision, self.remote_files("docs/brain"))
        self.assertIsNotNone(data["review"])

    def test_drafts_survive_a_conflict_and_new_files(self):
        rel = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        self.save()
        self.push_from_other(rel, page("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Theirs.\n")[1])
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Mine.\n")
        draft_a = self.put("concept", "DraftA", f"term_en: DraftA\n{SRC}")
        code, data, _ = run_cli("save", "-m", "pb(put): mine", str(self.wt / rel), cwd=self.repo)
        self.assertEqual(code, 1)
        draft_b = self.put("concept", "DraftB", f"term_en: DraftB\n{SRC}")
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Mine.\nTheirs.\n")
        code, data, err = run_cli("save", "--continue", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertTrue((self.wt / draft_a).is_file())
        self.assertTrue((self.wt / draft_b).is_file())

    def test_secrets_in_any_saved_file_block_the_save(self):
        self.write("brain/raw/2026/11/creds.txt", "password=hunter2hunter2hunter2\n", self.wt)
        code, data, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual(data["errors"][0]["code"], "secret")
        self.assertNotIn("brain/raw/2026/11/creds.txt", self.remote_files("docs/brain"))

    def test_continue_refuses_leftover_conflict_markers(self):
        rel = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        self.save()
        self.push_from_other(rel, page("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Theirs.\n")[1])
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Mine.\n")
        code, data, _ = self.save()
        self.assertEqual(code, 1)
        code, data, _ = run_cli("save", "--continue", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertEqual(data["errors"][0]["code"], "conflict-markers")
        self.assertNotIn("<<<<<<<", git(self.remote, "show", f"docs/brain:{rel}"))

    def test_link_to_an_unsaved_draft_blocks_the_partial_save(self):
        self.put("concept", "Draft", f"term_en: Draft\n{SRC}")
        mine = self.put("concept", "Mine", f"term_en: Mine\n{SRC}", "See [[Draft]].\n")
        code, data, _ = run_cli("save", "-m", "pb(put): mine", str(self.wt / mine), cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertEqual(data["errors"][0]["code"], "broken-link")

    def test_deleting_a_linked_page_blocks_the_save(self):
        target = self.put("concept", "Target", f"term_en: Target\n{SRC}")
        self.put("concept", "User", f"term_en: User\n{SRC}", "See [[Target]].\n")
        self.save()
        (self.wt / target).unlink()
        code, data, _ = self.save()
        self.assertEqual(code, 1)
        self.assertIn("Target", data["errors"][0]["message"])

    def test_paths_outside_the_copy_are_reported(self):
        code, data, _ = run_cli("save", "-m", "pb(put): x", str(self.repo / "brain/functional/x.md"), cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertEqual(data["errors"][0]["code"], "not-in-brain")
        self.assertFalse(data["saved"])

    def test_validate_takes_brain_prefixed_paths(self):
        rel = self.put("concept", "Broken", "term_en: [unclosed")
        code, data, _ = run_cli("validate", rel, cwd=self.repo)
        self.assertEqual(code, 1)
        code, data, _ = run_cli("validate", "brain/functional/concepts/Nope.md", cwd=self.repo)
        self.assertEqual(data["errors"][0]["code"], "unknown-path")

    def test_failed_rebase_without_conflict_is_not_a_conflict(self):
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        git(self.remote, "branch", "-D", "docs/brain")
        code, data, _ = self.save()
        self.assertIsNone(data["conflict"])
        self.assertTrue(data["errors"] or data["problems"])


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
