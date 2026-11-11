import unittest
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from pb_core.repo import brain_pr_body, ensure_brain_pr, request_reviewers

PR_URL = "https://github.com/o/r/pull/{}"


class FakeGh:
    """Stands in for repo.gh_json: records every call, answers like the GitHub REST API."""

    def __init__(self, open_prs=(), fail=()):
        self.calls = []
        self.open_prs = list(open_prs)
        self.fail = set(fail)  # "list", "open", "patch", "reviewers"

    def __call__(self, args):
        self.calls.append(list(args))
        path = args[1]
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        kind = ("reviewers" if path.endswith("/requested_reviewers") else "list" if method == "GET"
                else "open" if method == "POST" else "patch")
        if kind in self.fail:
            return None
        if kind == "list":
            return self.open_prs
        if kind == "open":
            return {"number": 7, "html_url": PR_URL.format(7), "user": {"login": "routine-bot"}}
        if kind == "patch":
            number = int(path.rsplit("/", 1)[1])
            return {"number": number, "html_url": PR_URL.format(number)}
        return {}

    def fields(self, kind):
        """The -f fields of the first call of this kind."""
        for args in self.calls:
            path = args[1]
            method = args[args.index("-X") + 1] if "-X" in args else "GET"
            if (kind == "open" and method == "POST" and path.endswith("/pulls")) or \
                    (kind == "patch" and method == "PATCH") or \
                    (kind == "reviewers" and path.endswith("/requested_reviewers")):
                return [args[i + 1] for i, a in enumerate(args) if a == "-f"]
        return None


class BrainPrBodyTest(unittest.TestCase):
    def test_body_names_merge_skill_when_behind(self):
        body = brain_pr_body("- decisions/X.md: decision accepted\n", 3, "main")
        self.assertIn("`docs/brain` is behind `main`: run `/pb:merge` to bring these changes to `main`", body)
        self.assertIn("decisions/X.md", body)

    def test_body_without_behind_has_no_notice(self):
        body = brain_pr_body("- decisions/X.md: decision accepted\n", 0, "main")
        self.assertNotIn("is behind", body)
        self.assertNotIn("/pb:merge", body)
        self.assertIn("decisions/X.md", body)

    def test_body_without_watched_changes_says_so(self):
        body = brain_pr_body("", 0, "main")
        self.assertIn("nothing on a watched point", body)


class EnsureBrainPrTest(unittest.TestCase):
    def test_opens_the_pr_when_none_is_open(self):
        gh = FakeGh()
        with mock.patch("pb_core.repo.gh_json", gh):
            url, number, problem, _ = ensure_brain_pr("o/r", "main", "the body")
        self.assertEqual((url, number, problem), (PR_URL.format(7), 7, None))
        self.assertEqual(gh.calls[0][:2], ["api", "repos/o/r/pulls?head=o:docs/brain&base=main&state=open"])
        self.assertEqual(gh.fields("open"), ["title=Brain updates", "head=docs/brain", "base=main", "body=the body"])

    def test_found_pr_gets_its_body_updated(self):
        gh = FakeGh(open_prs=[{"number": 12, "html_url": PR_URL.format(12)}])
        with mock.patch("pb_core.repo.gh_json", gh):
            url, number, problem, _ = ensure_brain_pr("o/r", "main", "new body")
        self.assertEqual((url, number, problem), (PR_URL.format(12), 12, None))
        self.assertIsNone(gh.fields("open"))
        patch = [args for args in gh.calls if "PATCH" in args][0]
        self.assertEqual(patch[1], "repos/o/r/pulls/12")
        self.assertEqual(gh.fields("patch"), ["title=Brain updates", "body=new body"])

    def test_found_pr_gets_the_configured_title(self):
        gh = FakeGh(open_prs=[{"number": 12, "html_url": PR_URL.format(12), "title": "Brain updates"}])
        with mock.patch("pb_core.repo.gh_json", gh):
            ensure_brain_pr("o/r", "main", "new body", "docs: brain updates")
        self.assertEqual(gh.fields("patch"), ["title=docs: brain updates", "body=new body"])

    def test_author_of_the_pr_is_returned(self):
        for gh, expected in ((FakeGh(), "routine-bot"),
                             (FakeGh(open_prs=[{"number": 12, "html_url": PR_URL.format(12),
                                                "user": {"login": "owner"}}]), "owner"),
                             (FakeGh(fail={"list"}), None)):
            with self.subTest(expected=expected), mock.patch("pb_core.repo.gh_json", gh):
                self.assertEqual(ensure_brain_pr("o/r", "main", "b")[3], expected)

    def test_unreachable_github_is_a_problem(self):
        with mock.patch("pb_core.repo.gh_json", FakeGh(fail={"list"})):
            url, number, problem, _ = ensure_brain_pr("o/r", "main", "b")
        self.assertEqual((url, number), (None, None))
        self.assertIn("GitHub could not be reached", problem)

    def test_failed_open_is_a_problem(self):
        with mock.patch("pb_core.repo.gh_json", FakeGh(fail={"open"})):
            url, number, problem, _ = ensure_brain_pr("o/r", "main", "b")
        self.assertEqual((url, number), (None, None))
        self.assertIn("could not be opened", problem)

    def test_failed_body_update_keeps_the_pr(self):
        gh = FakeGh(open_prs=[{"number": 12, "html_url": PR_URL.format(12)}], fail={"patch"})
        with mock.patch("pb_core.repo.gh_json", gh):
            url, number, problem, _ = ensure_brain_pr("o/r", "main", "b")
        self.assertEqual((url, number), (PR_URL.format(12), 12))
        self.assertIn("description", problem)


class RequestReviewersTest(unittest.TestCase):
    def test_users_and_teams_are_requested(self):
        gh = FakeGh()
        with mock.patch("pb_core.repo.gh_json", gh):
            problems = request_reviewers("o/r", 7, {"users": ["pm"], "teams": ["backend"]})
        self.assertEqual(problems, [])
        self.assertEqual(gh.calls[0][1], "repos/o/r/pulls/7/requested_reviewers")
        self.assertEqual(gh.fields("reviewers"), ["reviewers[]=pm", "team_reviewers[]=backend"])

    def test_no_reviewers_no_call(self):
        gh = FakeGh()
        with mock.patch("pb_core.repo.gh_json", gh):
            self.assertEqual(request_reviewers("o/r", 7, {"users": [], "teams": []}), [])
        self.assertEqual(gh.calls, [])

    def test_the_pr_author_is_never_requested(self):
        gh = FakeGh()
        with mock.patch("pb_core.repo.gh_json", gh):
            problems = request_reviewers("o/r", 7, {"users": ["Owner", "pm"], "teams": ["backend"]}, exclude=["owner"])
        self.assertEqual(problems, [])
        self.assertEqual(gh.fields("reviewers"), ["reviewers[]=pm", "team_reviewers[]=backend"])

    def test_only_the_author_listed_no_call(self):
        gh = FakeGh()
        with mock.patch("pb_core.repo.gh_json", gh):
            self.assertEqual(request_reviewers("o/r", 7, {"users": ["owner"], "teams": []}, exclude=["owner"]), [])
        self.assertEqual(gh.calls, [])

    def test_failed_request_is_a_problem(self):
        with mock.patch("pb_core.repo.gh_json", FakeGh(fail={"reviewers"})):
            problems = request_reviewers("o/r", 7, {"users": ["pm"], "teams": []})
        self.assertEqual(len(problems), 1)
        self.assertIn("reviewers", problems[0])


if __name__ == "__main__":
    unittest.main()
