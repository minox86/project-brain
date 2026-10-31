import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, page, files_of, run_cli

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
fixtures = json.load(open(os.environ["FAKE_GH_FIXTURES"]))
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:2] != ["api"] or sys.argv[2] not in fixtures:
    sys.stderr.write("HTTP 404: Not Found\\n")
    sys.exit(1)
sys.stdout.write(json.dumps(fixtures[sys.argv[2]]))
"""


def pr(number, merged_at, updated_at=None, body="Why we changed it.", title=None):
    return {"number": number, "title": title or f"PR {number}", "body": body, "merged_at": merged_at,
            "updated_at": updated_at or merged_at, "html_url": f"https://github.com/o/r/pull/{number}",
            "user": {"login": "someone"}}


def files(*names, additions=1, deletions=0):
    return [{"filename": n, "additions": additions, "deletions": deletions} for n in names]


LIST = "repos/o/r/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={}"
FILES = "repos/o/r/pulls/{}/files?per_page=100&page={}"


class PrsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = make_brain(base / "repo", {
            **files_of(page("module", "Billing", "paths: [services/billing/**]"),
                       page("module", "Web", "paths: [apps/web/**]")),
            "schema/sources.md": "---\ngithub: {repo: o/r}\n---\n# Sources\n",
        })
        bindir = base / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.fixtures = base / "fixtures.json"
        self.log = base / "gh.log"
        self.log.write_text("")
        self._env = {k: os.environ.get(k) for k in ("PATH", "FAKE_GH_FIXTURES", "FAKE_GH_LOG")}
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_GH_FIXTURES"] = str(self.fixtures)
        os.environ["FAKE_GH_LOG"] = str(self.log)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def serve(self, mapping):
        self.fixtures.write_text(json.dumps(mapping))

    def test_keeps_only_merged_prs_touching_modules(self):
        self.serve({
            LIST.format(1): [
                pr(4, "2026-10-31T09:00:00Z"),
                pr(3, None, updated_at="2026-10-31T08:00:00Z"),   # closed, not merged
                pr(2, "2026-10-30T10:00:00Z"),
                pr(1, "2026-10-20T10:00:00Z"),                    # before the cursor
            ],
            FILES.format(4, 1): files("services/billing/api.py", "docs/x.md", additions=10, deletions=2),
            FILES.format(2, 1): files("README.md"),
        })
        code, data, err = run_cli("prs", "--since", "2026-10-29T00:00:00Z", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual([p["number"] for p in data["prs"]], [4])
        found = data["prs"][0]
        self.assertEqual(found["modules"], ["Billing"])
        self.assertEqual(found["matched_files"], ["services/billing/api.py"])
        self.assertEqual((found["files"], found["additions"], found["deletions"]), (2, 20, 4))
        self.assertEqual(found["body"], "Why we changed it.")
        self.assertFalse(found["body_truncated"])
        self.assertNotIn("user", found)
        self.assertEqual(data["skipped"], [2])
        self.assertEqual(data["cursor"], "2026-10-31T09:00:00Z")
        self.assertNotIn("pulls/1/files", self.log.read_text())

    def test_paginates_list_and_files_and_stops_at_cursor(self):
        page1 = [pr(500 - i, "2026-10-31T10:00:00Z") for i in range(100)]
        self.serve({
            LIST.format(1): page1,
            LIST.format(2): [pr(9, "2026-10-30T10:00:00Z"), pr(8, "2026-10-01T10:00:00Z")],
            **{FILES.format(500 - i, 1): files("apps/web/a.ts") for i in range(1, 100)},
            FILES.format(500, 1): files(*[f"docs/{i}.md" for i in range(100)]),
            FILES.format(500, 2): files("services/billing/x.py"),
            FILES.format(9, 1): files("apps/web/b.ts"),
        })
        code, data, err = run_cli("prs", "--since", "2026-10-29T00:00:00Z", cwd=self.repo)
        self.assertEqual(code, 0, err)
        numbers = [p["number"] for p in data["prs"]]
        self.assertEqual(len(numbers), 101)
        self.assertIn(500, numbers)
        self.assertIn(9, numbers)
        self.assertNotIn(8, numbers)
        self.assertNotIn("page=3", self.log.read_text())

    def test_long_body_is_cut_and_flagged(self):
        self.serve({LIST.format(1): [pr(1, "2026-10-31T09:00:00Z", body="word " * 500)],
                    FILES.format(1, 1): files("apps/web/a.ts")})
        _, data, _ = run_cli("prs", "--since", "2026-10-29T00:00:00Z", cwd=self.repo)
        self.assertTrue(data["prs"][0]["body_truncated"])
        self.assertEqual(len(data["prs"][0]["body"].split()), 300)

    def test_nothing_new_keeps_cursor(self):
        self.serve({LIST.format(1): [pr(1, "2026-10-01T09:00:00Z")]})
        _, data, _ = run_cli("prs", "--since", "2026-10-29T00:00:00Z", cwd=self.repo)
        self.assertEqual((data["prs"], data["skipped"], data["cursor"]), ([], [], "2026-10-29T00:00:00Z"))

    def test_gh_failure_and_missing_repo(self):
        self.serve({})
        code, data, _ = run_cli("prs", "--since", "2026-10-29T00:00:00Z", cwd=self.repo)
        self.assertEqual((code, data["code"]), (2, "gh-failed"))
        (self.repo / "brain/schema/sources.md").write_text("---\ngithub: null\n---\n")
        code, data, _ = run_cli("prs", "--since", "2026-10-29T00:00:00Z", cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("repo", data["error"])

    def test_repo_flag_overrides_sources(self):
        self.serve({"repos/x/y/pulls?state=closed&sort=updated&direction=desc&per_page=100&page=1": []})
        code, data, err = run_cli("prs", "--since", "2026-10-29T00:00:00Z", "--repo", "x/y", cwd=self.repo)
        self.assertEqual((code, data["repo"]), (0, "x/y"), err)


if __name__ == "__main__":
    unittest.main()
