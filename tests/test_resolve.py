import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli


class ResolveTest(unittest.TestCase):
    def test_resolve_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp, files_of(
                page("concept", "Invoice", "term_en: Invoice\naliases: [Bill]"),
                page("feature", "Invoice Approval"),
                page("concept", "Invoce Line", "term_en: Invoice line"),
                page("module", "Billing", "paths: [x/**]"),
            ))
            code, data, _ = run_cli("resolve", "Invoice", cwd=repo)
            self.assertEqual(code, 0)
            c = data["candidates"]
            self.assertEqual((c[0]["title"], c[0]["match"], c[0]["score"]), ("Invoice", "title", 1.0))
            self.assertEqual(c[1]["match"], "partial")
            _, data, _ = run_cli("resolve", "bill", cwd=repo)
            self.assertEqual(data["candidates"][0]["match"], "alias")
            self.assertEqual(data["candidates"][1]["title"], "Billing")
            _, data, _ = run_cli("resolve", "Invoice", "--type", "feature", cwd=repo)
            self.assertEqual([x["title"] for x in data["candidates"]], ["Invoice Approval"])
            _, data, _ = run_cli("resolve", "Invoise", cwd=repo)
            self.assertEqual(data["candidates"][0]["match"], "fuzzy")

    def test_resolve_outside_brain(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, data, _ = run_cli("resolve", "x", cwd=tmp)
            self.assertEqual(code, 2)
            self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
