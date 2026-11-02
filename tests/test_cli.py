import os
import tempfile
import unittest

from helpers import run_cli


class CliTest(unittest.TestCase):
    def test_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.pop("PB_BRAIN", None)
            try:
                code, data, _ = run_cli("version", cwd=tmp)
            finally:
                if env is not None:
                    os.environ["PB_BRAIN"] = env
        self.assertEqual(code, 0)
        self.assertEqual(data["version"], "0.2.0")
        self.assertEqual(data["format"], 1)
        self.assertIsNone(data["brain"])

    def test_unknown_command_is_usage_error(self):
        code, _, _ = run_cli("nope")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
