import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli
from pb_core.context import path_matches


def billing_brain(tmp, extra=()):
    return make_brain(tmp, files_of(
        page("module", "Billing", 'paths: [services/billing/**]\ninterfaces: ["[[Invoice Events]]"]', "Owns invoices.\n"),
        page("module", "Web", "paths: [apps/web/]"),
        page("interface", "Billing API", 'kind: rest\nprovided_by: "[[Billing]]"\nconsumed_by: ["[[Web]]"]'),
        page("interface", "Invoice Events", "kind: event"),
        page("feature", "Invoice Approval", 'jira: [FIN-1]\nmodules: ["[[Billing]]"]\nconcepts: ["[[Invoice]]"]'),
        page("concept", "Invoice", "term_en: Invoice"),
        page("decision", "Single approver", 'area: functional\nstatus: accepted\naffects: ["[[Invoice Approval]]"]'),
        page("decision", "Old approver rule", 'area: functional\nstatus: superseded\naffects: ["[[Invoice Approval]]"]'),
        page("open-question", "Approval limits", 'area: functional\nstatus: open\naffects: ["[[Billing]]"]'),
        page("open-question", "Closed one", 'area: functional\nstatus: resolved\naffects: ["[[Billing]]"]'),
        *extra,
    ))


def titles(data):
    return sorted(p["title"] for p in data["pages"])


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_path_forms(self):
        target = "apps/billing/src/x.ts"
        for pattern in ("apps/billing/**", "apps/billing/", "apps/billing", "./apps/billing/**", "apps/*/src/*.ts"):
            with self.subTest(pattern=pattern):
                self.assertTrue(path_matches(pattern, target))
        self.assertFalse(path_matches("apps/billing/src/y.ts", target))
        self.assertTrue(path_matches("apps/billing/src/x.ts", target))
        self.assertFalse(path_matches("apps/bill", target))

    def test_context_by_paths_expands_interfaces_features_decisions(self):
        repo = billing_brain(self.tmp.name)
        code, data, _ = run_cli("context", "--paths", "services/billing/api/handler.py", cwd=repo)
        self.assertEqual(code, 0)
        self.assertEqual(data["seeds"], ["Billing"])
        self.assertEqual(titles(data), ["Approval limits", "Billing", "Billing API", "Invoice Approval",
                                        "Invoice Events", "Single approver"])
        md = data["markdown"]
        self.assertTrue(md.startswith("# Context: Billing"))
        self.assertLess(md.index("## Features"), md.index("## Modules"))
        self.assertIn("### Billing\n", md)

    def test_superseded_decision_and_resolved_question_excluded(self):
        repo = billing_brain(self.tmp.name)
        _, data, _ = run_cli("context", "--feature", "Invoice Approval", cwd=repo)
        self.assertNotIn("Old approver rule", titles(data))
        self.assertNotIn("Closed one", titles(data))
        self.assertIn("Single approver", titles(data))
        self.assertIn("Invoice", titles(data))

    def test_context_by_jira_via_field_and_sources(self):
        repo = billing_brain(self.tmp.name, [page("feature", "Refunds", 'sources: ["jira:FIN-2"]')])
        _, data, _ = run_cli("context", "--jira", "FIN-1", cwd=repo)
        self.assertEqual(data["seeds"], ["Invoice Approval"])
        _, data, _ = run_cli("context", "--jira", "FIN-2", cwd=repo)
        self.assertEqual(data["seeds"], ["Refunds"])

    def test_context_unknown_seed_returns_empty(self):
        repo = billing_brain(self.tmp.name)
        code, data, _ = run_cli("context", "--paths", "docs/readme.md", cwd=repo)
        self.assertEqual(code, 0)
        self.assertEqual((data["seeds"], data["pages"]), ([], []))

    def test_max_words_degrades_to_summary(self):
        long_body = "## Purpose\nShort first paragraph.\n\n" + "filler " * 300
        repo = billing_brain(self.tmp.name, [page("feature", "Big", 'summary: Big feature\nmodules: ["[[Billing]]"]', long_body)])
        _, data, _ = run_cli("context", "--paths", "services/billing/x", "--max-words", "150", cwd=repo)
        self.assertLessEqual(data["words"], 150)
        big = [p for p in data["pages"] if p["title"] == "Big"][0]
        self.assertEqual(big["included"], "summary")
        self.assertIn("Big feature", data["markdown"])
        self.assertIn("(see brain/functional/features/Big.md)", data["markdown"])

    def test_requires_exactly_one_seed_kind(self):
        repo = billing_brain(self.tmp.name)
        code, _, _ = run_cli("context", cwd=repo)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
