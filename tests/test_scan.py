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


if __name__ == "__main__":
    unittest.main()
