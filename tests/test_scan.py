import tempfile
import unittest
from pathlib import Path

from helpers import run_cli


def touch(root, rel, text="x"):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class ScanTest(unittest.TestCase):
    def test_scan_finds_modules_specs_adrs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rel in ("package.json", "README.md", "apps/web/package.json", "apps/web/README.md",
                        "services/billing/pyproject.toml", "services/billing/openapi.yaml",
                        "services/billing/events/asyncapi.yml", "protos/billing.proto",
                        "docs/adr/0001-use-rest.md", "docs/architecture/decisions/0002-x.md",
                        "node_modules/x/package.json", "brain/technical/modules/x.md",
                        ".github/CODEOWNERS", ".github/workflows/ci.yml", "tools/a/b/c/d/package.json"):
                touch(tmp, rel)
            code, data, err = run_cli("scan", "--repo", tmp)
            self.assertEqual(code, 0, err)
            self.assertEqual([(m["name"], m["path"], m["manifest"]) for m in data["modules"]],
                             [("web", "apps/web", "package.json"), ("billing", "services/billing", "pyproject.toml")])
            self.assertEqual([(s["path"], s["kind"]) for s in data["specs"]],
                             [("protos/billing.proto", "proto"),
                              ("services/billing/events/asyncapi.yml", "asyncapi"),
                              ("services/billing/openapi.yaml", "openapi")])
            self.assertEqual(data["adrs"], ["docs/adr/0001-use-rest.md", "docs/architecture/decisions/0002-x.md"])
            self.assertEqual(data["codeowners"], ".github/CODEOWNERS")
            self.assertEqual(data["readmes"], ["README.md", "apps/web/README.md"])
            self.assertEqual(data["ci"], [".github/workflows/ci.yml"])
            self.assertIn("apps", data["top_level"])
            self.assertNotIn("node_modules", data["top_level"])

    def test_scan_discovers_documentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            touch(tmp, "README.md", "# Product\n\none two three")
            touch(tmp, "ARCHITECTURE.md", "# Architecture\n\nalpha beta")
            touch(tmp, "docs/guides/billing.md", "Invoice flow\n\nwords here")
            touch(tmp, "docs/runbook.rst", "Runbook\n=======\n")
            touch(tmp, "docs/handbook.adoc", "= Handbook")
            touch(tmp, "apps/web/README.md", "# Web")
            touch(tmp, "apps/web/src/notes.md", "loose note")
            for rel in ("docs/adr/0001-use-rest.md", "CHANGELOG.md", "LICENSE.md", "CLAUDE.md", "AGENTS.md",
                        ".github/PULL_REQUEST_TEMPLATE.md", "apps/web/tests/fixtures/sample.md",
                        "node_modules/x/README.md", "brain/README.md", "docs/image.png"):
                touch(tmp, rel)
            code, data, err = run_cli("scan", "--repo", tmp)
            self.assertEqual(code, 0, err)
            docs = {d["path"]: d for d in data["docs"]}
            self.assertEqual(sorted(docs), ["ARCHITECTURE.md", "README.md", "apps/web/README.md",
                                            "apps/web/src/notes.md", "docs/guides/billing.md",
                                            "docs/handbook.adoc", "docs/runbook.rst"])
            self.assertEqual(docs["README.md"]["kind"], "readme")
            self.assertEqual(docs["README.md"]["title"], "Product")
            self.assertEqual(docs["README.md"]["words"], 5)
            self.assertEqual(docs["ARCHITECTURE.md"]["kind"], "root")
            self.assertEqual(docs["docs/guides/billing.md"]["kind"], "docs")
            self.assertEqual(docs["docs/guides/billing.md"]["title"], "Invoice flow")
            self.assertEqual(docs["docs/runbook.rst"]["title"], "Runbook")
            self.assertEqual(docs["docs/handbook.adoc"]["title"], "Handbook")
            self.assertEqual(docs["apps/web/src/notes.md"]["kind"], "other")
            self.assertEqual(data["docs_words"], sum(d["words"] for d in data["docs"]))


if __name__ == "__main__":
    unittest.main()
