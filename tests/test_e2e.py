import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import assert_links_resolve, page, run_cli
from test_gitops import GIT_ENV, git


class EndToEndTest(unittest.TestCase):
    def test_e2e_scaffold_write_validate_generate_context(self):
        saved = {k: os.environ.get(k) for k in GIT_ENV}
        os.environ.update(GIT_ENV)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                (repo / "services/billing").mkdir(parents=True)
                (repo / "services/billing/api.py").write_text("def approve(): ...\n")
                git(repo, "init", "-q", "-b", "main")
                git(repo, "add", "-A")
                git(repo, "commit", "-qm", "init")
                code, _, err = run_cli("scaffold", "--repo", repo, "--product", "Fatture Pro")
                self.assertEqual(code, 0, err)
                types = sorted(p.stem for p in (repo / "brain/.pb/schema/types").glob("*.md"))
                self.assertEqual(types, ["concept", "contract", "decision", "environment", "feature", "integration",
                                         "module", "open-question", "process", "role"])
                git(repo, "checkout", "-qb", "feat/approval")
                run_cli("commit", "--skill", "init", "-m", "create brain", cwd=repo)
                pages = [
                    page("module", "Billing", "paths: [services/billing/**]\nsummary: Invoices and payments",
                         "## Responsibility\nOwns every [[Invoice]] and the [[Billing API]].\n"),
                    page("contract", "Billing API", "kind: api\nprovided_by: Billing"),
                    page("feature", "Invoice Approval", "jira: [FIN-1]\nmodules: [Billing]\nconcepts: [Invoice]",
                         "An [[Fattura|invoice]] is approved in [[Billing#Responsibility]].\n"),
                    page("concept", "Invoice", "term_en: Invoice\nterm_it: Fattura\naliases: [Fattura]"),
                    page("process", "Order to cash", "applies_to: [Invoice Approval]", "Goes through [[Invoice Approval]].\n"),
                    page("decision", "Single approver", "area: functional\naffects: [Billing, Invoice Approval]",
                         "See [[Approval limits]].\n"),
                    page("open-question", "Approval limits", "area: functional\naffects: [Invoice Approval]"),
                ]
                for rel, text in pages:
                    target = repo / "brain" / rel
                    target.write_text(text)
                code, data, _ = run_cli("validate", cwd=repo)
                self.assertEqual(code, 0, data)
                code, data, err = run_cli("save", cwd=repo)
                self.assertEqual(code, 0, (data, err))
                self.assertEqual(len(data["normalised"]), 7)
                feature = (repo / "brain/functional/features/Invoice Approval.md").read_text()
                self.assertIn("---\n# Invoice Approval\n\nAn [invoice](../concepts/Invoice.md) is approved in "
                              "[Billing](../../technical/modules/Billing.md#responsibility).", feature)
                code, data, err = run_cli("commit", "--skill", "put", "-m", "seed", cwd=repo)
                self.assertEqual(code, 0, err)
                self.assertIn("brain/functional/features/Invoice Approval.md", data["files"])
                code, data, _ = run_cli("generate", cwd=repo)
                self.assertEqual(code, 0)
                self.assertIn("| [Invoice](Invoice.md) | Fattura |",
                              (repo / "brain/functional/concepts/README.md").read_text())
                self.assertIn("### Order to cash", (repo / "brain/.pb/context/Invoice Approval.md").read_text())
                self.assertIn("- [Billing](Billing.md) — Invoices and payments",
                              (repo / "brain/technical/modules/README.md").read_text())
                markdown = [p for p in (repo / "brain").rglob("*.md") if ".pb/toolkit" not in p.as_posix()]
                self.assertGreater(assert_links_resolve(self, markdown), 30)
                code, data, _ = run_cli("context", "--paths", "services/billing/api.py", cwd=repo)
                self.assertEqual(sorted(p["title"] for p in data["pages"]),
                                 sorted(["Approval limits", "Billing", "Billing API", "Invoice", "Invoice Approval",
                                         "Order to cash", "Single approver"]))
                _, data, _ = run_cli("context", "--jira", "FIN-1", cwd=repo)
                self.assertEqual(len(data["pages"]), 7)
                code, data, _ = run_cli("lint", cwd=repo)
                self.assertNotIn("broken-link", {f["code"] for f in data["findings"]})
                out = subprocess.run(["python3", "brain/.pb/toolkit/pb.py", "validate"], cwd=str(repo),
                                     capture_output=True, text=True)
                self.assertEqual(out.returncode, 0, out.stdout)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
