import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from helpers import make_brain, page, run_cli
from test_gitops import GitRepoCase, git
from test_prs import FAKE_GH

SRC = 'sources: ["jira:FIN-1"]'
BASE_PAGES = [
    page("module", "Billing", f"paths: [services/billing/**]\n{SRC}", "Owns [[Invoice]].\n"),
    page("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Billed by [[Billing]].\n"),
    page("feature", "Approval", f"status: planned\n{SRC}", "Approves an [[Invoice]].\n"),
]


def codes_for(data, path, key="warnings"):
    return sorted(f["code"] for f in data[key] if f["path"] == path)


class BrainRepoCase(GitRepoCase):
    review_policy = True

    def setUp(self):
        super().setUp()
        for rel, text in BASE_PAGES:
            self.write("brain/" + rel, text)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pages")
        git(self.repo, "push", "-q", "origin", "main")

    def put(self, type_, title, meta="", body="Body.\n"):
        rel, text = page(type_, title, meta, body)
        self.write("brain/" + rel, text)
        return rel

    def policy(self, text):
        self.write("brain/.pb/schema/review.md", f"---\n{text}\n---\n# Review policy\n")

    def review(self, *args):
        code, data, err = run_cli("review", *args, cwd=self.repo)
        self.assertEqual(code, 0, err)
        return data

    def flagged(self, data):
        return {item["path"]: item["reasons"] for item in data["review"]}


class NoiseTest(BrainRepoCase):
    def validate(self):
        code, data, err = run_cli("validate", cwd=self.repo)
        self.assertEqual(code, 0, data)
        return data

    def test_untouched_pages_are_not_checked(self):
        self.write("brain/functional/features/Approval.md",
                   page("feature", "Approval", "", "Approves an [[Invoice]] today.\n")[1])
        git(self.repo, "commit", "-qam", "legacy page")
        self.assertEqual(self.validate()["warnings"], [])

    def test_possible_duplicate_and_orphan_only_for_new_pages(self):
        rel = self.put("feature", "Approvals", SRC, "Approves an [[Invoice]].\n")
        self.assertEqual(codes_for(self.validate(), rel), ["new-orphan", "possible-duplicate"])
        self.assertEqual(codes_for(self.validate(), "functional/features/Approval.md"), [])

    def test_linked_new_page_is_not_orphan(self):
        rel = self.put("concept", "Approver", f"term_en: Approver\n{SRC}", "Signs an [[Invoice]].\n")
        self.put("feature", "Approval", f"status: planned\n{SRC}", "An [[Approver]] approves an [[Invoice]].\n")
        self.assertEqual(codes_for(self.validate(), rel), [])

    def test_missing_source_on_updated_page(self):
        rel = self.put("feature", "Approval", "status: planned", "Approves an [[Invoice]].\n")
        self.assertEqual(codes_for(self.validate(), rel), ["missing-source"])

    def test_body_noise(self):
        quote = "> " + " ".join(["word"] * 45) + "\n"
        rel = self.put("feature", "Approval", f"status: planned\n{SRC}",
                       "Approves an [[Invoice]].\n## Update 2026-10-31\nThis sprint we ship it.\n" + quote)
        data = self.validate()
        self.assertEqual(codes_for(data, rel), ["ephemeral", "log-heading", "verbatim"])
        lines = {f["code"]: f["message"] for f in data["warnings"]}
        self.assertIn("line 2", lines["log-heading"])
        self.assertIn("'This sprint'", lines["ephemeral"])

    def test_code_blocks_are_not_noise(self):
        rel = self.put("feature", "Approval", f"status: planned\n{SRC}",
                       "Approves an [[Invoice]].\n```\n// TODO today\n```\n")
        self.assertEqual(codes_for(self.validate(), rel), [])

    def test_base_option_and_no_git(self):
        self.put("feature", "Approval", "status: planned", "Approves an [[Invoice]].\n")
        git(self.repo, "commit", "-qam", "drop sources")
        _, data, _ = run_cli("validate", cwd=self.repo)
        self.assertEqual(data["warnings"], [])
        _, data, _ = run_cli("validate", "--base", "HEAD~1", cwd=self.repo)
        self.assertEqual(codes_for(data, "functional/features/Approval.md"), ["missing-source"])
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp, dict([page("feature", "Lonely")]))
            code, data, _ = run_cli("validate", cwd=repo)
            self.assertEqual((code, data["warnings"]), (0, []))


class PolicyValidationTest(BrainRepoCase):
    def test_preset_policy_is_valid(self):
        code, data, _ = run_cli("validate", cwd=self.repo)
        self.assertEqual(code, 0, data)

    def test_bad_policy(self):
        self.policy("direct_min_confidence: sure\nreviewers: {design: [a]}\n"
                    "watch:\n  - {type: persona}\n  - {type: feature, change: rename, colour: red}\n  - {fields: [x]}")
        code, data, _ = run_cli("validate", cwd=self.repo)
        self.assertEqual(code, 1)
        messages = [f["message"] for f in data["errors"] if f["code"] == "bad-review-policy"]
        self.assertEqual(len(messages), 6, messages)


class ReviewTest(BrainRepoCase):
    def test_no_policy_sends_everything_direct(self):
        (self.repo / "brain/.pb/schema/review.md").unlink()
        rel = self.put("decision", "Single approver", f"area: technical\n{SRC}")
        data = self.review("--confidence", f"brain/{rel}=low")
        self.assertEqual((data["route"], data["direct"]), ("direct", [rel]))

    def test_watched_decision_and_reviewers_by_area(self):
        self.policy('direct_min_confidence: high\nreviewers: {technical: ["@dev-lead", "acme/backend"], '
                    'functional: [pm], ux: [designer]}\nwatch: [{type: decision, why: "decisions"}]')
        rel = self.put("decision", "Single approver", f"area: technical\n{SRC}", "Affects [[Approval]].\n")
        self.put("feature", "Approval", f"status: planned\n{SRC}", "Approves an [[Invoice]] once.\n")
        data = self.review()
        self.assertEqual(data["route"], "pr")
        self.assertEqual(self.flagged(data), {rel: ["watch: decisions"]})
        self.assertEqual(data["direct"], ["functional/features/Approval.md"])
        self.assertEqual(data["reviewers"], {"areas": ["technical"], "handles": ["dev-lead", "acme/backend"],
                                             "users": ["dev-lead"], "teams": ["backend"]})
        self.assertIn(f"`{rel}`", data["markdown"])

    def test_area_reviewers_are_listed_even_with_nothing_flagged(self):
        self.policy('reviewers: {technical: ["@dev-lead", "acme/backend"], functional: [pm]}')
        data = self.review()
        self.assertEqual(data["review"], [])
        self.assertEqual(data["area_reviewers"]["technical"],
                         {"areas": ["technical"], "handles": ["dev-lead", "acme/backend"], "users": ["dev-lead"],
                          "teams": ["backend"]})
        self.assertEqual(data["area_reviewers"]["ux"]["handles"], [])

    def test_confidence_threshold(self):
        self.policy("direct_min_confidence: high")
        rel = self.put("feature", "Approval", f"status: planned\n{SRC}", "Approves an [[Invoice]] once.\n")
        data = self.review("--confidence", f"{rel}=medium", "brain/other/Nope.md=low")
        self.assertEqual(self.flagged(data), {rel: ["confidence: medium"]})
        self.assertEqual(data["ignored_confidence"], ["brain/other/Nope.md"])
        self.policy("direct_min_confidence: medium")
        self.assertEqual(self.review("--confidence", f"{rel}=medium")["route"], "direct")
        with self.assertRaises(AssertionError):
            self.review("--confidence", f"{rel}=sure")

    def test_field_rule_matches_only_when_the_field_changes(self):
        self.policy("watch: [{type: feature, fields: [status]}]")
        rel = self.put("feature", "Approval", f"status: planned\n{SRC}", "Approves an [[Invoice]] once.\n")
        self.assertEqual(self.review()["route"], "direct")
        self.put("feature", "Approval", f"status: released\n{SRC}", "Approves an [[Invoice]].\n")
        self.assertEqual(self.flagged(self.review()), {rel: ["watch: feature · fields status"]})

    def test_delete_rule_and_cross_area_asks_everyone(self):
        self.policy("reviewers: {technical: [t], functional: [f], ux: [u]}\n"
                    "watch: [{type: '*', change: delete}]")
        (self.repo / "brain/functional/features/Approval.md").unlink()
        data = self.review()
        self.assertEqual(data["review"][0]["change"], "delete")
        self.assertEqual(data["reviewers"]["users"], ["f"])
        self.policy("reviewers: {technical: [t], functional: [f], ux: [u]}\nwatch: [{type: open-question}]")
        self.write("brain/functional/features/Approval.md", BASE_PAGES[2][1])
        self.put("open-question", "Who approves", "area: functional\n" + SRC)
        self.assertEqual(self.review()["reviewers"]["users"], ["f"])
        self.put("open-question", "Who approves", SRC)
        self.assertEqual(self.review()["reviewers"]["users"], ["t", "f", "u"])

    def test_a_change_that_only_rewrites_links_is_not_watched(self):
        self.policy("watch:\n  - {type: concept, change: update}\n  - {type: module, change: update}")
        run_cli("links", cwd=self.repo)  # [[Invoice]] -> [Invoice](...), and a heading
        data = self.review()
        self.assertEqual(data["review"], [])
        self.write("brain/functional/concepts/Invoice.md",
                   (self.repo / "brain/functional/concepts/Invoice.md").read_text() + "A real change.\n")
        self.assertEqual([i["path"] for i in self.review()["review"]], ["functional/concepts/Invoice.md"])

    def test_page_linking_a_flagged_new_page_is_flagged_too(self):
        self.policy("watch: [{type: decision}]")
        decision = self.put("decision", "Single approver", f"area: functional\n{SRC}")
        feature = self.put("feature", "Approval", f"status: planned\n{SRC}",
                           "Approves an [[Invoice]], see [[Single approver]].\n")
        flagged = self.flagged(self.review())
        self.assertEqual(flagged[feature], ["links [[Single approver]], new and under review"])
        self.assertIn(decision, flagged)

    def test_noise_flags_pages(self):
        self.policy("noise_to_review: true")
        rel = self.put("feature", "Approval", "status: planned", "Approves an [[Invoice]].\n")
        self.assertEqual(self.flagged(self.review()), {rel: ["noise: missing-source"]})
        self.policy("noise_to_review: false")
        self.assertEqual(self.review()["route"], "direct")

    def test_base_for_pull_requests(self):
        self.policy("watch: [{type: decision}]")
        git(self.repo, "commit", "-qam", "policy")
        base = git(self.repo, "rev-parse", "HEAD")
        rel = self.put("decision", "Single approver", f"area: ux\n{SRC}", "Affects [[Approval]].\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "decision")
        self.assertEqual(self.review()["route"], "direct")
        self.assertEqual(list(self.flagged(self.review("--base", base))), [rel])


class RoutineSplitTest(BrainRepoCase):
    def setUp(self):
        super().setUp()
        self.policy('reviewers: {technical: ["acme/backend"], functional: [pm]}\n'
                    "watch: [{type: decision}]\ndirect_min_confidence: high")
        self.write("brain/.pb/schema/sources.md", "---\ngithub: {repo: o/r}\n---\n# Sources\n")
        git(self.repo, "commit", "-qam", "policy")
        git(self.repo, "push", "-q", "origin", "main")
        base = Path(self.tmp.name)
        bindir = base / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.log = base / "gh.log"
        self.log.write_text("")
        fixtures = base / "fixtures.json"
        fixtures.write_text(json.dumps({
            "repos/o/r/pulls?head=o:docs/brain&base=main&state=open": [],
            "repos/o/r/pulls": {"number": 7, "html_url": "https://github.com/o/r/pull/7"},
            "repos/o/r/pulls/7/requested_reviewers": {},
        }))
        saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_GH_FIXTURES", "FAKE_GH_LOG")}
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_GH_FIXTURES"] = str(fixtures)
        os.environ["FAKE_GH_LOG"] = str(self.log)
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in saved.items()])

    def test_without_watched_pages_no_reviewer_is_requested(self):
        run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Billed by [[Billing]] monthly.\n")
        code, data, _ = run_cli("routine", "finish", "--branch", "docs/brain", "-m", "m", cwd=self.repo)
        self.assertEqual((code, data["watched"], data["pr"]), (0, [], "https://github.com/o/r/pull/7"))
        self.assertNotIn("review", data)
        self.assertNotIn("requested_reviewers", self.log.read_text())


class TemplatesTest(unittest.TestCase):
    def test_validate_workflow_never_merges_and_guards_the_brain_pr(self):
        from helpers import ROOT
        text = (ROOT / "templates/github/pb-validate.yml").read_text()
        self.assertIn("--brain brain validate", text)
        self.assertNotIn("paths:", text)
        self.assertIn("github.head_ref == 'docs/brain'", text)
        self.assertIn("head.repo.full_name == github.repository", text)
        self.assertIn("grep -v -E '^brain/' ", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("--approve", text)
        self.assertIn("AUTHOR: ${{ github.event.pull_request.user.login }}", text)
        self.assertIn('[ "${user,,}" = "${AUTHOR,,}" ] && continue', text)
        # Schema or toolkit touched: the technical area reviewers (spec section 7).
        self.assertIn(".area_reviewers.technical.users[]?", text)
        self.assertIn(".area_reviewers.technical.teams[]?", text)
        self.assertIn("no reviewer could be derived", text)
        self.assertIn("contents: read", text)

    def test_scaffold_ships_the_review_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            git(Path(tmp), "init", "-q", "-b", "main")
            code, data, err = run_cli("scaffold", "--product", "Acme", "--repo", tmp)
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(tmp) / "brain/.pb/schema/review.md").is_file())
            code, data, _ = run_cli("validate", cwd=tmp)
            self.assertEqual(code, 0, data)


if __name__ == "__main__":
    unittest.main()
