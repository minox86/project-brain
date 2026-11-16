import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import make_brain, run_cli
from pb_core import repo


def clone(tmp, url, files=None):
    root = make_brain(tempfile.mkdtemp(dir=tmp), files)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "remote", "add", "origin", url], cwd=root, check=True)
    return root


class GithubHostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(repo.use_host, None)
        patch = mock.patch.dict(os.environ)
        patch.start()
        os.environ.pop("GH_HOST", None)
        self.addCleanup(patch.stop)

    def test_origin_urls(self):
        for url, expected in (
                ("git@github.com:acme/mono.git", ("github.com", "acme/mono")),
                ("https://github.com/acme/mono", ("github.com", "acme/mono")),
                ("https://github.acme.com/team/mono.git", ("github.acme.com", "team/mono")),
                ("git@github.acme.com:team/mono.git", ("github.acme.com", "team/mono")),
                ("ssh://git@GitHub.acme.com:2222/team/mono.git", ("github.acme.com", "team/mono")),
                ("https://user@github.acme.com/team/mono/", ("github.acme.com", "team/mono")),
                ("/srv/git/mono.git", (None, None)),
                ("../remote.git", (None, None)),
                ("file:///srv/git/team/mono.git", (None, None))):
            with self.subTest(url=url):
                self.assertEqual(repo.origin_parts(clone(self.tmp.name, url)), expected)

    def test_gh_api_goes_to_the_enterprise_host_of_the_origin(self):
        root = clone(self.tmp.name, "git@github.acme.com:team/mono.git")
        code, data, _ = run_cli("version", cwd=root)
        self.assertEqual((code, data["github_host"]), (0, "github.acme.com"))
        self.assertEqual(repo.gh_command(["api", "repos/team/mono/pulls", "-X", "POST"]),
                         ["gh", "api", "--hostname", "github.acme.com", "repos/team/mono/pulls", "-X", "POST"])
        self.assertEqual(repo.gh_command(["auth", "status"]), ["gh", "auth", "status"])
        self.assertEqual(repo.origin_repo(root), "team/mono")

    def test_github_com_needs_no_host(self):
        root = clone(self.tmp.name, "https://github.com/acme/mono.git")
        self.assertIsNone(run_cli("version", cwd=root)[1]["github_host"])
        self.assertEqual(repo.gh_command(["api", "user"]), ["gh", "api", "user"])

    def test_host_from_sources_wins_over_an_ssh_alias(self):
        sources = {".pb/schema/sources.md": "---\ngithub: {repo: team/mono, host: github.acme.com}\n---\n# Sources\n"}
        root = clone(self.tmp.name, "git@work:team/mono.git", sources)
        self.assertEqual(run_cli("version", cwd=root)[1]["github_host"], "github.acme.com")
        self.assertEqual(run_cli("version", cwd=clone(self.tmp.name, "git@work:team/mono.git"))[1]["github_host"],
                         "work")

    def test_the_user_gh_host_is_left_alone(self):
        root = clone(self.tmp.name, "git@github.acme.com:team/mono.git")
        run_cli("version", cwd=root)
        with mock.patch.dict(os.environ, {"GH_HOST": "other.acme.com"}):
            self.assertEqual(repo.gh_command(["api", "user"]), ["gh", "api", "user"])

    def test_prs_are_read_from_the_enterprise_host(self):
        root = clone(self.tmp.name, "https://github.acme.com/team/mono.git")
        bindir = Path(tempfile.mkdtemp(dir=self.tmp.name))
        log = bindir / "calls"
        gh = bindir / "gh"
        gh.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\necho "[]"\n')
        gh.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}):
            code, data, err = run_cli("prs", "--since", "2026-11-01T00:00:00Z", "--repo", "team/mono", cwd=root)
        self.assertEqual(code, 0, err)
        self.assertTrue(log.read_text().startswith("api --hostname github.acme.com repos/team/mono/pulls?"))

    def test_ci_workflow_sets_the_host_for_gh(self):
        text = (Path(__file__).resolve().parents[1] / "templates/github/pb-validate.yml").read_text()
        self.assertEqual(text.count('export GH_HOST="${SERVER_URL#*://}"'), 2)
        self.assertEqual(text.count("GH_ENTERPRISE_TOKEN: ${{ github.token }}"), 2)


if __name__ == "__main__":
    unittest.main()
