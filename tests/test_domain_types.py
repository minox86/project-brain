import shutil
import tempfile
import unittest

from helpers import ROOT, make_brain, page, files_of, run_cli

DOMAIN = ROOT / "presets" / "domain-types"


class DomainTypesTest(unittest.TestCase):
    def test_catalogue_is_not_a_preset(self):
        self.assertFalse((DOMAIN / "VERSION").exists())
        self.assertTrue((DOMAIN / "README.md").is_file())

    def test_every_domain_type_validates_with_the_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp, files_of(page("feature", "Approval", "capability: Invoicing")))
            types = sorted(DOMAIN.glob("*.md"))
            types = [t for t in types if t.name != "README.md"]
            self.assertEqual([t.stem for t in types], ["edition", "metric", "process", "regulation", "rule"])
            for t in types:
                shutil.copy(str(t), str(repo / "brain/schema/types" / t.name))
            pages = {
                "rule": ("functional/rules", "basis: law\nregulation: \"[[E-invoicing]]\""),
                "regulation": ("functional/regulations", "authority: Agenzia delle Entrate"),
                "process": ("functional/processes", ""),
                "metric": ("functional/metrics", "unit: \"%\""),
                "edition": ("functional/editions", "kind: plan"),
            }
            titles = {"rule": "Rounding", "regulation": "E-invoicing", "process": "Order to cash",
                      "metric": "Approval rate", "edition": "Premium"}
            for name, (folder, meta) in pages.items():
                path = repo / "brain" / folder / f"{titles[name]}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'---\ntype: {name}\ntitle: "{titles[name]}"\n{meta}\n'
                                f'applies_to: ["[[Approval]]"]\nsources: ["url:https://example.com"]\n---\nBody.\n')
            code, data, err = run_cli("validate", cwd=repo)
            self.assertEqual(code, 0, (data, err))
            self.assertEqual(data["errors"], [])
            self.assertFalse([w for w in data["warnings"] if w["code"] in ("unknown-field", "link-type")], data)
            _, ctx, _ = run_cli("context", "--feature", "Approval", cwd=repo)
            self.assertEqual(sorted(p["title"] for p in ctx["pages"]),
                             ["Approval", "Approval rate", "E-invoicing", "Order to cash", "Premium", "Rounding"])


if __name__ == "__main__":
    unittest.main()
