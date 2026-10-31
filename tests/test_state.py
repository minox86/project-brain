import json
import tempfile
import unittest

from helpers import make_brain, run_cli


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_brain(self.tmp.name)

    def cli(self, *args):
        return run_cli(*args, cwd=self.repo)

    def test_set_get_roundtrip_json_values(self):
        code, _, _ = self.cli("state", "set", "teams", "prod-general", '{"cursor": "2026-10-30T22:00:00Z"}')
        self.assertEqual(code, 0)
        self.cli("state", "set", "teams", "count", "3")
        _, data, _ = self.cli("state", "get", "teams", "prod-general")
        self.assertEqual(data["value"], {"cursor": "2026-10-30T22:00:00Z"})
        _, data, _ = self.cli("state", "get", "teams")
        self.assertEqual(data["value"]["count"], 3)
        _, data, _ = self.cli("state", "get", "confluence", "missing")
        self.assertIsNone(data["value"])
        stored = json.loads((self.repo / "brain/.pb/state/teams.json").read_text())
        self.assertEqual(stored["count"], 3)

    def test_unknown_source_is_usage_error(self):
        code, data, _ = self.cli("state", "get", "slack")
        self.assertEqual(code, 2)
        self.assertIn("error", data)

    def test_bad_json_value_is_usage_error(self):
        code, _, _ = self.cli("state", "set", "teams", "k", "{bad")
        self.assertEqual(code, 2)

    def test_correction_appends_and_escapes_pipes(self):
        args = ["correction", "--page", "decisions/X.md", "--wrong", "uses a|b", "--right", "uses c",
                "--evidence", "services/billing/api.py", "--today", "2026-10-31"]
        self.assertEqual(self.cli(*args)[0], 0)
        self.cli(*args)
        text = (self.repo / "brain/.pb/corrections.md").read_text()
        self.assertTrue(text.startswith("# Corrections\n\n| Date | Page | Wrong | Right | Evidence |"))
        self.assertEqual(text.count("| 2026-10-31 | decisions/X.md | uses a\\|b | uses c | services/billing/api.py |"), 2)

    def test_suppress_dedup(self):
        self.cli("state", "suppress", "teams", "Invoices need two approvers")
        _, data, _ = self.cli("state", "suppress", "teams", "Invoices need two approvers")
        self.assertEqual(data["suppressed"], ["Invoices need two approvers"])


if __name__ == "__main__":
    unittest.main()
