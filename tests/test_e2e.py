import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import page, run_cli
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
                git(repo, "checkout", "-qb", "feat/approval")
                run_cli("commit", "--skill", "init", "-m", "create brain", cwd=repo)
                pages = [
                    page("module", "Billing", "paths: [services/billing/**]\nsummary: Invoices and payments",
                         "## Responsibility\nOwns invoices.\n"),
                    page("interface", "Billing API", 'kind: rest\nprovided_by: "[[Billing]]"'),
                    page("feature", "Invoice Approval", 'jira: [FIN-1]\nmodules: ["[[Billing]]"]\nconcepts: ["[[Invoice]]"]'),
                    page("concept", "Invoice", "term_en: Invoice\nterm_it: Fattura"),
                    page("decision", "Single approver", 'area: functional\naffects: ["[[Billing]]", "[[Invoice Approval]]"]'),
                    page("open-question", "Approval limits", 'area: functional\naffects: ["[[Invoice Approval]]"]'),
                ]
                for rel, text in pages:
                    target = repo / "brain" / rel
                    target.write_text(text)
                code, data, _ = run_cli("validate", cwd=repo)
                self.assertEqual(code, 0, data)
                code, data, err = run_cli("commit", "--skill", "put", "-m", "seed", cwd=repo)
                self.assertEqual(code, 0, err)
                self.assertEqual(len(data["files"]), 6)
                code, _, _ = run_cli("generate", cwd=repo)
                self.assertEqual(code, 0)
                self.assertIn("| [[Invoice\\|Invoice]] | Fattura |", (repo / "brain/glossary.md").read_text())
                self.assertTrue((repo / "brain/context/Invoice Approval.md").is_file())
                self.assertIn("- [[Billing]] — Invoices and payments", (repo / "brain/index.md").read_text())
                code, data, _ = run_cli("context", "--paths", "services/billing/api.py", cwd=repo)
                self.assertEqual(sorted(p["title"] for p in data["pages"]),
                                 sorted(["Approval limits", "Billing", "Billing API", "Invoice", "Invoice Approval",
                                         "Single approver"]))
                _, data, _ = run_cli("context", "--jira", "FIN-1", cwd=repo)
                self.assertEqual(len(data["pages"]), 6)
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
