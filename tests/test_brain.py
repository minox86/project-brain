import os
import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, page, files_of, run_cli
from pb_core import links
from pb_core.brain import Brain, find_brain


class BrainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_find_brain_walks_up(self):
        repo = make_brain(self.tmp.name)
        deep = repo / "apps" / "web" / "src"
        deep.mkdir(parents=True)
        self.assertEqual(find_brain(deep, None), (repo / "brain").resolve())
        self.assertIsNone(find_brain(Path(tempfile.gettempdir()), None))

    def test_find_brain_needs_the_marker_under_pb(self):
        repo = make_brain(self.tmp.name)
        self.assertTrue((repo / "brain/.pb/schema/VERSION").is_file())
        self.assertFalse((repo / "brain" / "schema").exists())
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        old = Path(other.name)
        (old / "brain" / "schema").mkdir(parents=True)
        (old / "brain" / "schema" / "VERSION").write_text("1\n")  # the layout before 0.6: not a brain
        self.assertIsNone(find_brain(old, None))

    def test_find_brain_env_and_explicit(self):
        repo = make_brain(self.tmp.name)
        self.assertEqual(find_brain(Path("/"), str(repo / "brain")), (repo / "brain").resolve())
        self.assertEqual(find_brain(Path("/"), str(repo)), (repo / "brain").resolve())
        os.environ["PB_BRAIN"] = str(repo / "brain")
        try:
            self.assertEqual(find_brain(Path("/"), None), (repo / "brain").resolve())
        finally:
            del os.environ["PB_BRAIN"]

    def test_find_brain_ignores_a_leftover_managed_copy(self):
        import shutil
        from test_gitops import GIT_ENV, git
        repo = make_brain(Path(self.tmp.name) / "repo")
        env = {k: os.environ.get(k) for k in GIT_ENV}
        os.environ.update(GIT_ENV)
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in env.items()])
        git(repo, "init", "-q", "-b", "main")
        leftover = repo / ".git" / "pb" / "brain-worktree" / "brain"
        shutil.copytree(str(repo / "brain"), str(leftover))
        self.assertEqual(find_brain(repo, None), (repo / "brain").resolve())
        self.assertEqual(find_brain(repo / "brain", None), (repo / "brain").resolve())

    def test_version_reports_brain(self):
        repo = make_brain(self.tmp.name)
        code, data, _ = run_cli("version", cwd=repo)
        self.assertEqual(code, 0)
        self.assertEqual(Path(data["brain"]), (repo / "brain").resolve())

    def test_types_loaded_from_preset(self):
        brain = Brain(make_brain(self.tmp.name) / "brain")
        self.assertEqual(len(brain.types), 10)
        self.assertTrue(brain.types["decision"].system)
        self.assertFalse(brain.types["feature"].system)
        self.assertEqual(brain.types["concept"].max_words, 250)
        self.assertEqual(brain.types["module"].required, ["paths"])
        self.assertEqual(brain.config["digest_retention_days"], 30)

    def test_pages_and_lookup(self):
        repo = make_brain(self.tmp.name, files_of(
            page("concept", "Invoice", "term_en: Invoice\naliases: [Bill]", "An invoice is a document. With more words.\n"),
            page("module", "Billing", "paths: [services/billing/**]"),
        ))
        brain = Brain(repo / "brain")
        self.assertEqual(sorted(p.title for p in brain.pages()), ["Billing", "Invoice"])
        self.assertEqual(brain.lookup("invoice")[1], "title")
        found, how = brain.lookup("bill")
        self.assertEqual((found.title, how), ("Invoice", "alias"))
        self.assertEqual(brain.lookup("nope"), (None, None))
        inv = brain.by_title["invoice"]
        self.assertEqual(inv.words, 8)
        self.assertEqual(inv.rel, "functional/concepts/Invoice.md")

    def test_bad_frontmatter_goes_to_load_errors(self):
        repo = make_brain(self.tmp.name, {
            **files_of(page("module", "Billing", "paths: [a/**]")),
            "technical/modules/Broken.md": "---\ntype: module\ntitle: [unclosed\n---\nx",
        })
        brain = Brain(repo / "brain")
        self.assertEqual([p.title for p in brain.pages()], ["Billing"])
        self.assertEqual(brain.load_errors[0]["path"], "technical/modules/Broken.md")

    def test_non_page_files_ignored(self):
        repo = make_brain(self.tmp.name, {
            "README.md": "# index",
            "functional/features/README.md": "# Features",
            ".pb/digests/2026-10-30.md": "# digest",
            ".pb/raw/2026/10/x.md": "---\nkind: file\n---\ntext",
            "functional/features/notes.txt": "x",
        })
        self.assertEqual(Brain(repo / "brain").pages(), [])

    def test_is_generated_needs_the_brain_prefix_and_a_known_folder(self):
        from pb_core.brain import is_generated
        folders = {"functional/features", "decisions"}
        for path in ("brain/README.md", "brain/functional/features/README.md", "brain/.pb/context/A.md",
                     "brain/.pb/backlinks.json"):
            self.assertTrue(is_generated(path, folders), path)
        for path in ("README.md", "functional/features/README.md", "brain/functional/README.md",
                     "brain/functional/features/sub/README.md", "brain/.pb/toolkit/README.md",
                     "brain/functional/features/A.md", "apps/README.md"):
            self.assertFalse(is_generated(path, folders), path)

    def test_old_format_brain_is_named(self):
        old = Path(self.tmp.name)
        (old / "brain" / "schema").mkdir(parents=True)
        (old / "brain" / "schema" / "VERSION").write_text("1\n")
        code, data, _ = run_cli("validate", cwd=old)
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "old-format")
        self.assertIn("remove `brain/` and create it again with /pb:init", data["error"])

    def test_wikilink_variants(self):
        self.assertEqual(links.extract("see [[A|x]], [[A#h]] and [[A#h|x]] or [[ B ]]"), ["A", "A", "A", "B"])


if __name__ == "__main__":
    unittest.main()
