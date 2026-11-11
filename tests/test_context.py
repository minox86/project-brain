import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli
from pb_core.context import path_matches


def billing_brain(tmp, extra=()):
    return make_brain(tmp, files_of(
        page("module", "Billing", "paths: [services/billing/**]", "Owns invoices.\n"),
        page("module", "Web", "paths: [apps/web/]"),
        page("contract", "Billing API", 'kind: api\nprovided_by: Billing'),
        page("contract", "Invoice Events", 'kind: event\nprovided_by: Web\nconsumed_by: [Billing]'),
        page("contract", "Web Theme", "kind: ui"),
        page("feature", "Invoice Approval", 'jira: [FIN-1]\nmodules: [Billing]\nconcepts: [Invoice]'),
        page("concept", "Invoice", "term_en: Invoice"),
        page("decision", "Single approver", 'area: functional\nstatus: accepted\naffects: [Invoice Approval]'),
        page("decision", "Old approver rule", 'area: functional\nstatus: superseded\naffects: [Invoice Approval]'),
        page("open-question", "Approval limits", 'area: functional\nstatus: open\naffects: [Billing]'),
        page("open-question", "Closed one", 'area: functional\nstatus: resolved\naffects: [Billing]'),
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

    def test_context_by_paths_expands_contracts_features_decisions(self):
        repo = billing_brain(self.tmp.name)
        code, data, _ = run_cli("context", "--paths", "services/billing/api/handler.py", cwd=repo)
        self.assertEqual(code, 0)
        self.assertEqual(data["seeds"], ["Billing"])
        self.assertEqual(titles(data), ["Approval limits", "Billing", "Billing API", "Invoice", "Invoice Approval",
                                        "Invoice Events", "Single approver"])
        md = data["markdown"]
        self.assertTrue(md.startswith("# Context: Billing"))
        self.assertLess(md.index("## Features"), md.index("## Modules"))
        self.assertLess(md.index("## Modules"), md.index("## Contracts"))
        self.assertIn("### Billing\n", md)

    def test_context_follows_roles_integrations_and_domain_types(self):
        repo = billing_brain(self.tmp.name, [
            page("role", "Accountant"),
            page("integration", "SDI", 'kind: api\nused_by: [Billing]'),
            page("feature", "Approval", 'capability: Invoicing\nroles: [Accountant]\nmodules: [Billing]'),
        ])
        rule = repo / "brain/.pb/schema/types/rule.md"
        rule.write_text("---\nname: rule\narea: functional\nfolder: functional/rules\nmax_words: 300\n"
                        "fields:\n  status: {kind: enum, values: [active, retired], default: active}\n"
                        "  applies_to: {kind: list, of: link}\nrequired: []\n---\n# Rule\n")
        for title, status in (("Rounding", "active"), ("Old rounding", "retired")):
            path = repo / f"brain/functional/rules/{title}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'---\ntype: rule\ntitle: "{title}"\nstatus: {status}\n'
                            f'applies_to: [Approval]\n---\nRule body.\n')
        _, data, _ = run_cli("context", "--feature", "Approval", cwd=repo)
        got = titles(data)
        for title in ("Accountant", "SDI", "Rounding", "Billing"):
            self.assertIn(title, got)
        self.assertNotIn("Old rounding", got)
        md = data["markdown"]
        self.assertIn("## Roles", md)
        self.assertIn("## Integrations", md)
        self.assertIn("## Rules\n\n### Rounding", md)
        self.assertLess(md.index("## Rules"), md.index("## Modules"))

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

    def test_context_by_jira_matches_every_feature_carrying_the_key(self):
        repo = billing_brain(self.tmp.name, [page("feature", "Approval Rules", 'jira: [FIN-9, fin-1]')])
        _, data, _ = run_cli("context", "--jira", "fin-1", cwd=repo)
        self.assertEqual(sorted(data["seeds"]), ["Approval Rules", "Invoice Approval"])
        code, data, _ = run_cli("context", "--jira", "FIN-404", cwd=repo)
        self.assertEqual(code, 0)
        self.assertEqual((data["seeds"], data["pages"], data["markdown"]), ([], [], ""))

    def test_context_unknown_seed_returns_empty(self):
        repo = billing_brain(self.tmp.name)
        code, data, _ = run_cli("context", "--paths", "docs/readme.md", cwd=repo)
        self.assertEqual(code, 0)
        self.assertEqual((data["seeds"], data["pages"]), ([], []))

    def test_max_words_degrades_to_summary(self):
        long_body = "## Purpose\nShort first paragraph.\n\n" + "filler " * 300
        repo = billing_brain(self.tmp.name, [page("feature", "Big", 'summary: Big feature\nmodules: [Billing]', long_body)])
        _, data, _ = run_cli("context", "--paths", "services/billing/x", "--max-words", "150", cwd=repo)
        self.assertLessEqual(data["words"], 150)
        big = [p for p in data["pages"] if p["title"] == "Big"][0]
        self.assertEqual(big["included"], "summary")
        self.assertIn("Big feature", data["markdown"])
        # PB context answers with links valid from the repo root; the written packs keep theirs.
        self.assertIn("Big feature ([Big](brain/functional/features/Big.md))", data["markdown"])

    def test_cli_pack_links_are_repo_paths(self):
        repo = billing_brain(self.tmp.name, [page("role", "Accountant"),
                                            page("feature", "Pay", "", "By an [[Accountant]].\n")])
        _, data, _ = run_cli("context", "--feature", "Pay", cwd=repo)
        self.assertIn("By an [Accountant](brain/functional/roles/Accountant.md).", data["markdown"])
        run_cli("generate", cwd=repo)
        self.assertIn("By an [Accountant](../../functional/roles/Accountant.md).",
                      (repo / "brain/.pb/context/Pay.md").read_text())

    def test_requires_exactly_one_seed_kind(self):
        repo = billing_brain(self.tmp.name)
        code, _, _ = run_cli("context", cwd=repo)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
