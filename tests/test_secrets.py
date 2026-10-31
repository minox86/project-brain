import unittest

import helpers  # noqa: F401
from pb_core.secrets import scan


class SecretsTest(unittest.TestCase):
    def test_patterns(self):
        samples = {
            "aws": "key AKIAABCDEFGHIJKLMNOP here",
            "github": "token ghp_" + "a" * 36,
            "github-pat": "github_pat_" + "A1_" * 15,
            "slack": "xoxb-1234567890-abcdef",
            "private-key": "-----BEGIN RSA PRIVATE KEY-----",
            "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            "url-credentials": "postgres://admin:hunter22@db.internal:5432/app",
            "assignment": "password: Sup3rS3cretValue",
        }
        for kind, text in samples.items():
            with self.subTest(kind=kind):
                found = scan("line one\n" + text)
                self.assertTrue(found, kind)
                self.assertEqual(found[0]["line"], 2)

    def test_placeholders_and_prose_not_flagged(self):
        for text in ("password: ${DB_PASSWORD}", "the password is rotated monthly",
                     "api_key: <your-key>", "https://example.com/path", "token: {{TOKEN}}"):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])


if __name__ == "__main__":
    unittest.main()
