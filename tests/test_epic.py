import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli


def epic_brain(tmp, extra=()):
    return make_brain(tmp, files_of(
        page("module", "Billing", "paths: [services/billing/**]"),
        page("module", "Web", "paths: [apps/web/**]"),
        page("feature", "Invoice Approval", 'jira: [FIN-1]\nmodules: ["[[Billing]]"]\nconcepts: ["[[Invoice]]"]'),
        page("feature", "Reports", 'modules: ["[[Web]]"]'),
        page("concept", "Invoice", "term_en: Invoice"),
        page("epic", "Multi-level approval", 'jira: FIN-100\nstatus: active\nfeatures: ["[[Invoice Approval]]"]',
             "## Goal\nApproval chains.\n"),
        page("epic", "Legacy export", 'jira: FIN-50\nstatus: done\nupdated: 2026-01-01\nfeatures: ["[[Invoice Approval]]"]'),
        page("epic", "Web revamp", 'jira: FIN-200\nmodules: ["[[Web]]"]'),
        page("decision", "Max three levels", 'area: functional\naffects: ["[[Multi-level approval]]"]'),
        page("open-question", "Who approves level 3", 'area: functional\naffects: ["[[Multi-level approval]]"]'),
        *extra,
    ))


def titles(data):
    return sorted(p["title"] for p in data["pages"])


class EpicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_preset_epic_validates(self):
        repo = epic_brain(self.tmp.name)
        code, data, err = run_cli("validate", cwd=repo)
        self.assertEqual(code, 0, (data, err))

    def test_epic_requires_jira_key(self):
        repo = epic_brain(self.tmp.name, [page("epic", "No key", "status: active")])
        code, data, _ = run_cli("validate", cwd=repo)
        self.assertEqual(code, 1)
        self.assertIn("No key", str(data))

    def test_context_by_epic_key_expands_features_decisions_questions(self):
        repo = epic_brain(self.tmp.name)
        _, data, _ = run_cli("context", "--jira", "fin-100", cwd=repo)
        self.assertEqual(data["seeds"], ["Multi-level approval"])
        self.assertEqual(titles(data), ["Billing", "Invoice", "Invoice Approval", "Max three levels",
                                        "Multi-level approval", "Who approves level 3"])
        md = data["markdown"]
        self.assertLess(md.index("## Epics"), md.index("## Features"))

    def test_feature_context_includes_active_epics_only(self):
        repo = epic_brain(self.tmp.name)
        _, data, _ = run_cli("context", "--feature", "Invoice Approval", cwd=repo)
        self.assertIn("Multi-level approval", titles(data))
        self.assertIn("Max three levels", titles(data))
        self.assertNotIn("Legacy export", titles(data))

    def test_paths_context_includes_active_epics_on_module(self):
        repo = epic_brain(self.tmp.name)
        _, data, _ = run_cli("context", "--paths", "apps/web/src/a.ts", cwd=repo)
        self.assertIn("Web revamp", titles(data))
        self.assertIn("Reports", titles(data))

    def test_closed_epic_still_reachable_as_seed(self):
        repo = epic_brain(self.tmp.name)
        _, data, _ = run_cli("context", "--jira", "FIN-50", cwd=repo)
        self.assertEqual(data["seeds"], ["Legacy export"])

    def test_generate_packs_for_active_epics_and_archives_done(self):
        repo = epic_brain(self.tmp.name)
        code, _, err = run_cli("generate", "--today", "2026-10-31", cwd=repo)
        self.assertEqual(code, 0, err)
        brain = repo / "brain"
        packs = sorted(p.name for p in (brain / "context").iterdir())
        self.assertEqual(packs, ["Invoice Approval.md", "Multi-level approval.md", "Reports.md", "Web revamp.md"])
        index = (brain / "index.md").read_text()
        self.assertIn("## Epics", index)
        self.assertIn("[[Multi-level approval]] (active)", index)
        self.assertNotIn("[[Legacy export]]", index)

    def test_lint_flags_archivable_epic(self):
        repo = epic_brain(self.tmp.name)
        _, data, _ = run_cli("lint", "--today", "2026-10-31", cwd=repo)
        codes = {(f["code"], f["path"]) for f in data["findings"]}
        self.assertIn(("archivable", "epics/Legacy export.md"), codes)


if __name__ == "__main__":
    unittest.main()
