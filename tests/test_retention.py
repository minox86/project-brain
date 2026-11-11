import datetime
import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli

from pb_core.brain import Brain
from pb_core.generate import generate
from pb_core.retention import apply_retention

TODAY = datetime.date(2026, 11, 11)


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def brain(self, files):
        repo = make_brain(self.tmp.name, files)
        return repo / "brain"

    def test_old_closed_decision_is_flagged_and_leaves_index(self):
        root = self.brain(files_of(page("decision", "Old", "area: ux\nstatus: superseded\nupdated: 2026-01-01")))
        result = apply_retention(Brain(root), TODAY)
        self.assertEqual(result["archived"], ["decisions/Old.md"])
        self.assertIn("archived: true", (root / "decisions/Old.md").read_text())
        generate(Brain(root))
        index = (root / "decisions/README.md").read_text()
        self.assertNotIn("[Old]", index)
        self.assertIn("Archived: 1 pages (not listed).", index)

    def test_flag_goes_before_closing_fence_and_touches_nothing_else(self):
        root = self.brain(files_of(page("decision", "Old", "area: ux\nstatus: superseded\nupdated: 2026-01-01", "Body.\n---\nMore.\n")))
        path = root / "decisions/Old.md"
        before = path.read_text()
        apply_retention(Brain(root), TODAY)
        self.assertEqual(path.read_text(), before.replace("updated: 2026-01-01\n---\n", "updated: 2026-01-01\narchived: true\n---\n", 1))

    def test_existing_archived_key_is_replaced_not_duplicated(self):
        root = self.brain(files_of(page("decision", "Old", "area: ux\nstatus: superseded\nupdated: 2026-01-01\narchived: false")))
        path = root / "decisions/Old.md"
        self.assertEqual(apply_retention(Brain(root), TODAY)["archived"], ["decisions/Old.md"])
        text = path.read_text()
        self.assertEqual(text.count("archived:"), 1)
        self.assertIn("\narchived: true\n", text)
        self.assertNotIn("archived: false", text)
        self.assertEqual(apply_retention(Brain(root), TODAY)["archived"], [])
        self.assertEqual(path.read_text(), text)

    def test_recent_or_open_pages_are_not_flagged(self):
        root = self.brain(files_of(
            page("decision", "Recent", "area: ux\nstatus: superseded\nupdated: 2026-10-01"),
            page("decision", "Live", "area: ux\nstatus: accepted\nupdated: 2026-01-01"),
            page("feature", "Approval", "updated: 2026-01-01"),
        ))
        self.assertEqual(apply_retention(Brain(root), TODAY)["archived"], [])
        self.assertNotIn("archived", (root / "decisions/Live.md").read_text())

    def test_retention_is_idempotent(self):
        root = self.brain(files_of(page("open-question", "Q", "area: ux\nstatus: resolved\nupdated: 2026-01-01")))
        self.assertEqual(apply_retention(Brain(root), TODAY)["archived"], ["open-questions/Q.md"])
        text = (root / "open-questions/Q.md").read_text()
        self.assertEqual(apply_retention(Brain(root), TODAY)["archived"], [])
        self.assertEqual((root / "open-questions/Q.md").read_text(), text)
        self.assertEqual(text.count("archived: true"), 1)

    def test_old_digest_deleted_by_retention_not_by_generate(self):
        root = self.brain({".pb/digests/2026-01-01.md": "old", ".pb/digests/2026-11-01.md": "kept", ".pb/digests/notes.md": "x"})
        digest = root / ".pb/digests/2026-01-01.md"
        generate(Brain(root))
        self.assertTrue(digest.exists())
        result = apply_retention(Brain(root), TODAY)
        self.assertEqual(result["deleted"], [".pb/digests/2026-01-01.md"])
        self.assertFalse(digest.exists())
        self.assertTrue((root / ".pb/digests/2026-11-01.md").exists())
        self.assertTrue((root / ".pb/digests/notes.md").exists())

    def test_cli_retention(self):
        repo = make_brain(self.tmp.name, files_of(page("decision", "Old", "area: ux\nstatus: superseded\nupdated: 2026-01-01")))
        code, data, err = run_cli("retention", "--today", "2026-11-11", cwd=repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"archived": ["decisions/Old.md"], "deleted": []})
        code, _, _ = run_cli("generate", "--today", "2026-11-11", cwd=repo)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
