import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli


class LintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def lint(self, files, repo_files=()):
        repo = make_brain(self.tmp.name, files)
        for rel in repo_files:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("x")
        return run_cli("lint", "--today", "2026-10-31", cwd=repo)

    def codes(self, data):
        return sorted({f["code"] for f in data["findings"]})

    def linked_module(self):
        return [page("module", "Billing", "paths: [services/billing/**]"),
                page("feature", "F", 'modules: ["[[Billing]]"]')]

    def test_empty_brain_lint_clean(self):
        code, data, _ = self.lint({})
        self.assertEqual(code, 0, data)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["stats"]["pages"], 0)

    def test_validate_errors_included(self):
        code, data, _ = self.lint(files_of(page("decision", "X", "area: legal")))
        self.assertEqual(code, 1)
        self.assertIn("bad-enum", self.codes(data))

    def test_over_budget(self):
        _, data, _ = self.lint(files_of(*self.linked_module(), page("concept", "Invoice", 'term_en: Invoice', "w " * 201 + "[[F]]")),
                               ["services/billing/a.py"])
        self.assertIn("over-budget", self.codes(data))

    def test_duplicate_candidate(self):
        _, data, _ = self.lint(files_of(
            page("feature", "Invoice approval flow", "", "[[Invoice approval flows]]"),
            page("feature", "Invoice approval flows", "", "[[Invoice approval flow]]"),
        ))
        dup = [f for f in data["findings"] if f["code"] == "duplicate-candidate"]
        self.assertEqual(len(dup), 1)
        self.assertEqual(len(dup[0]["related"]), 1)

    def test_orphan(self):
        _, data, _ = self.lint(files_of(page("feature", "Lonely")))
        self.assertEqual(self.codes(data), ["orphan"])

    def test_stale_open_question(self):
        _, data, _ = self.lint(files_of(*self.linked_module(),
                                        page("open-question", "Q", 'area: ux\nstatus: open\nupdated: 2026-09-01\naffects: ["[[F]]"]')),
                               ["services/billing/a.py"])
        self.assertEqual(self.codes(data), ["stale-open-question"])

    def test_archivable(self):
        _, data, _ = self.lint(files_of(*self.linked_module(),
                                        page("decision", "D", 'area: ux\nstatus: superseded\nupdated: 2026-01-01\naffects: ["[[F]]"]')),
                               ["services/billing/a.py"])
        self.assertEqual(self.codes(data), ["archivable"])

    def test_dead_module_paths(self):
        _, data, _ = self.lint(files_of(*self.linked_module()), ["node_modules/services/billing/x.js"])
        self.assertEqual(self.codes(data), ["dead-module-paths"])

    def test_live_module_paths(self):
        code, data, _ = self.lint(files_of(*self.linked_module()), ["services/billing/src/a.py"])
        self.assertEqual(code, 0, data)

    def test_superseded_referenced(self):
        _, data, _ = self.lint(files_of(
            *self.linked_module(),
            page("decision", "Old", 'area: ux\nstatus: superseded\nupdated: 2026-10-30\naffects: ["[[F]]"]'),
            page("decision", "New", 'area: ux\nsupersedes: "[[Old]]"\naffects: ["[[F]]"]'),
            page("open-question", "Q", 'area: ux\nupdated: 2026-10-30\naffects: ["[[Old]]"]'),
        ), ["services/billing/a.py"])
        hits = [f for f in data["findings"] if f["code"] == "superseded-referenced"]
        self.assertEqual([f["path"] for f in hits], ["open-questions/Q.md"])


if __name__ == "__main__":
    unittest.main()
