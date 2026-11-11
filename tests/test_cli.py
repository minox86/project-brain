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

    def test_old_save_options_and_workspace_command_are_gone(self):
        for argv in (("workspace", "sync"), ("save", "-m", "x"), ("save", "--continue"),
                     ("save", "--force-review")):
            with self.subTest(argv=argv):
                code, data, _ = run_cli(*argv)
                self.assertEqual(code, 2)
                self.assertIn("unrecognized arguments" if argv[0] == "save" else "invalid choice", data["error"])


if __name__ == "__main__":
    unittest.main()
