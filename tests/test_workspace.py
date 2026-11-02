import json
import os
import stat
import unittest
from pathlib import Path

from helpers import page, run_cli
from test_gitops import GitRepoCase, git

SRC = "sources: [jira:FIN-1]"
PR = {"number": 7, "html_url": "https://github.com/o/r/pull/7"}
OPEN_PROMOTION = [{"url": "https://github.com/o/r/pull/3"}]

# A fake `gh` answering from a fixtures dict: api calls by path, other commands by their non-flag words.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
fixtures = json.load(open(os.environ["FAKE_GH_FIXTURES"]))
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
args = sys.argv[1:]
key = args[1] if args[:1] == ["api"] and len(args) > 1 else " ".join(a for a in args if not a.startswith("-"))
for k, v in fixtures.items():
    if key == k or (args[:1] != ["api"] and key.startswith(k)):
        sys.stdout.write(json.dumps(v))
        sys.exit(0)
sys.stderr.write("HTTP 404: Not Found\\n")
sys.exit(1)
"""


class FakeGhMixin:
    def fake_gh(self, fixtures):
        base = Path(self.tmp.name)
        bindir = base / "bin"
        bindir.mkdir(exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.gh_log = base / "gh.log"
        self.gh_log.write_text("")
        self.gh_fixtures = base / "fixtures.json"
        self.gh_fixtures.write_text(json.dumps(fixtures))
        saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_GH_FIXTURES", "FAKE_GH_LOG")}
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_GH_FIXTURES"] = str(self.gh_fixtures)
        os.environ["FAKE_GH_LOG"] = str(self.gh_log)
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in saved.items()])

    def set_fixture(self, key, value):
        data = json.loads(self.gh_fixtures.read_text())
        data[key] = value
        self.gh_fixtures.write_text(json.dumps(data))


class NoBrainTest(GitRepoCase):
    def test_sync_without_docs_brain_says_no_brain(self):
        code, data, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "no-brain")


class WorkspaceCase(FakeGhMixin, GitRepoCase):
    review_policy = True

    def setUp(self):
        super().setUp()
        self.write("brain/schema/review.md",
                   "---\nreviewers: {technical: [\"acme/backend\"], functional: [pm]}\n"
                   "watch: [{type: decision}]\ndirect_min_confidence: high\nnoise_to_review: true\n---\n# Review\n")
        self.write("brain/schema/sources.md", "---\ngithub: {repo: o/r}\n---\n# Sources\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "policy")
        git(self.repo, "push", "-q", "origin", "main", "main:refs/heads/docs/brain")
        self.fake_gh({"pr list": [], "repos/o/r/pulls": PR, "repos/o/r/pulls/7/requested_reviewers": {}})
        code, data, err = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.wt = Path(data["worktree"])

    def put(self, type_, title, meta=SRC, body="Body.\n", root=None):
        rel, text = page(type_, title, meta, body)
        self.write("brain/" + rel, text, root or self.wt)
        return "brain/" + rel

    def save(self, *extra):
        return run_cli("save", "-m", "pb(put): test", *extra, cwd=self.repo)

    def remote_files(self, ref):
        return git(self.remote, "ls-tree", "-r", "--name-only", ref, "brain/").splitlines()

    def other_clone(self):
        other = Path(self.tmp.name) / "other"
        if not other.exists():
            git(Path(self.tmp.name), "clone", "-q", "-b", "docs/brain", str(self.remote), str(other))
        git(other, "pull", "-q", "origin", "docs/brain")
        return other

    def push_from_other(self, rel, text):
        other = self.other_clone()
        self.write(rel, text, other)
        git(other, "add", "-A")
        git(other, "commit", "-qm", "theirs")
        git(other, "push", "-q", "origin", "HEAD:docs/brain")


class SyncTest(WorkspaceCase):
    def test_copy_lives_in_git_dir_and_user_checkout_untouched(self):
        self.assertIn(".git", self.wt.parts)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual(git(self.wt, "rev-parse", "HEAD"), git(self.remote, "rev-parse", "docs/brain"))

    def test_sync_moves_to_latest_brain(self):
        rel = "brain/" + page("concept", "Remote", f"term_en: Remote\n{SRC}")[0]
        self.push_from_other(rel, page("concept", "Remote", f"term_en: Remote\n{SRC}")[1])
        code, data, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(code, 0)
        self.assertTrue((self.wt / rel).is_file())

    def test_sync_keeps_unsaved_pages(self):
        rel = self.put("concept", "Draft", f"term_en: Draft\n{SRC}")
        self.push_from_other("brain/functional/concepts/Other.md", page("concept", "Other", f"term_en: Other\n{SRC}")[1])
        code, data, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(data["leftovers"], [rel])
        self.assertTrue((self.wt / rel).is_file())

    def test_busy_when_another_live_process_holds_the_lock(self):
        lock = self.wt.parent / "lock"
        lock.write_text(str(os.getppid()))
        code, data, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertEqual(data["code"], "busy")
        lock.write_text("999999")  # a dead process: taken over
        code, _, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(code, 0)


class SaveTest(WorkspaceCase):
    def test_save_pushes_to_docs_brain_and_opens_the_promotion_pr(self):
        rel = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        main_before = git(self.remote, "rev-parse", "main")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertTrue(data["saved"] and data["pushed"])
        self.assertIn(rel, self.remote_files("docs/brain"))
        self.assertEqual(git(self.remote, "rev-parse", "main"), main_before)
        self.assertEqual(git(self.remote, "branch", "--list", "pb/*"), "")
        calls = self.gh_log.read_text()
        self.assertIn("head=docs/brain", calls)
        self.assertIn("base=main", calls)
        self.assertEqual(data["promotion"], PR["html_url"])
        self.assertEqual(data["unpushed"], 0)
        self.assertEqual(data["problems"], [])

    def test_open_promotion_pr_is_reused(self):
        self.set_fixture("pr list", OPEN_PROMOTION)
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertEqual(data["promotion"], OPEN_PROMOTION[0]["url"])
        self.assertNotIn("pulls -X POST", self.gh_log.read_text())

    def test_without_gh_the_save_still_lands(self):
        os.environ["PATH"] = os.environ["PATH"].split(os.pathsep, 1)[1]
        rel = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertIn(rel, self.remote_files("docs/brain"))
        self.assertIsNone(data["promotion"])
        self.assertEqual(len(data["problems"]), 1)

    def test_watched_page_goes_to_review_pr_towards_docs_brain(self):
        concept = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        decision = self.put("decision", "Single approver", f"area: technical\n{SRC}")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        review = data["review"]
        self.assertTrue(review["branch"].startswith("pb/review/"))
        self.assertEqual(review["pr"], PR["html_url"])
        self.assertIn(decision, self.remote_files(review["branch"]))
        self.assertIn(concept, self.remote_files("docs/brain"))
        self.assertNotIn(decision, self.remote_files("docs/brain"))
        self.assertEqual(git(self.remote, "rev-parse", f"{review['branch']}~1"),
                         git(self.remote, "rev-parse", "docs/brain"))
        calls = self.gh_log.read_text()
        self.assertIn(f"head={review['branch']} -f base=docs/brain", calls)
        self.assertIn("team_reviewers[]=backend", calls)
        self.assertFalse((self.wt / decision).exists())
        self.assertEqual(data["unpushed"], 0)

    def test_interactive_save_ignores_noise(self):
        rel = self.put("concept", "Invoice", "term_en: Invoice")  # missing-source noise
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertIsNone(data["review"])
        self.assertIn(rel, self.remote_files("docs/brain"))

    def test_force_review_holds_everything(self):
        self.write("brain/schema/brain.md", (self.wt / "brain/schema/brain.md").read_text() + "\n", self.wt)
        code, data, err = self.save("--force-review")
        self.assertEqual(code, 0, err)
        self.assertFalse(data["pushed"])
        self.assertEqual(data["review"]["pages"], ["schema/brain.md"])
        self.assertIn("Configuration or toolkit change", self.gh_log.read_text())

    def test_errors_on_touched_pages_block_the_save(self):
        rel = self.put("concept", "Broken", "term_en: [unclosed")
        code, data, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual(data["errors"][0]["path"], rel[len("brain/"):])
        self.assertNotIn(rel, self.remote_files("docs/brain"))

    def test_errors_elsewhere_do_not_block(self):
        self.push_from_other("brain/functional/concepts/Bad.md", "---\ntype: concept\ntitle: [x\n---\n")
        run_cli("workspace", "sync", cwd=self.repo)
        rel = self.put("concept", "Fine", f"term_en: Fine\n{SRC}")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertIn(rel, self.remote_files("docs/brain"))

    def test_concurrent_save_is_rebased(self):
        mine = self.put("concept", "Mine", f"term_en: Mine\n{SRC}")
        theirs = "brain/" + page("concept", "Theirs", f"term_en: Theirs\n{SRC}")[0]
        self.push_from_other(theirs, page("concept", "Theirs", f"term_en: Theirs\n{SRC}")[1])
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        files = self.remote_files("docs/brain")
        self.assertIn(mine, files)
        self.assertIn(theirs, files)

    def test_conflict_is_resolved_then_continued(self):
        rel = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        self.save()
        run_cli("workspace", "sync", cwd=self.repo)
        self.push_from_other(rel, page("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Theirs.\n")[1])
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Mine.\n")
        code, data, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual(data["conflict"]["files"], [rel])
        self.assertIn("<<<<<<<", (self.wt / rel).read_text())
        code, data, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertTrue(data["rebase_in_progress"])
        self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}", "Mine.\nTheirs.\n")
        code, data, err = run_cli("save", "--continue", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertTrue(data["pushed"])
        self.assertIn("Mine.\nTheirs.", git(self.remote, "show", f"docs/brain:{rel}"))

    def test_offline_save_is_kept_and_goes_out_later(self):
        hidden = self.remote.with_name("away.git")
        self.remote.rename(hidden)
        rel = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertTrue(data["saved"])
        self.assertFalse(data["pushed"])
        self.assertEqual(data["unpushed"], 1)
        code, data, _ = run_cli("workspace", "sync", cwd=self.repo)
        self.assertEqual(data["unpushed"], 1)
        self.assertTrue((self.wt / rel).is_file())
        hidden.rename(self.remote)
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertTrue(data["pushed"])
        self.assertIn(rel, self.remote_files("docs/brain"))

    def test_held_pages_never_reach_docs_brain_after_a_failed_send(self):
        hidden = self.remote.with_name("away.git")
        self.remote.rename(hidden)
        decision = self.put("decision", "Single approver", f"area: technical\n{SRC}")
        self.save()
        hidden.rename(self.remote)
        concept = self.put("concept", "Invoice", f"term_en: Invoice\n{SRC}")
        code, data, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertIn(concept, self.remote_files("docs/brain"))
        self.assertNotIn(decision, self.remote_files("docs/brain"))
        self.assertIn(decision, self.remote_files(data["review"]["branch"]))


class RoutineTest(WorkspaceCase):
    def test_routine_on_docs_brain_opens_the_promotion_pr(self):
        clone = self.other_clone()
        code, data, err = run_cli("routine", "start", "--branch", "docs/brain", cwd=clone)
        self.assertEqual(code, 0, err)
        rel = "brain/schema/brain.md"  # not a page: no noise warning holds it
        self.write(rel, (clone / rel).read_text() + "\n", clone)
        code, data, err = run_cli("routine", "finish", "--branch", "docs/brain", "-m", "pb(routine): sync",
                                  cwd=clone)
        self.assertEqual(code, 0, err)
        self.assertTrue(data["committed"], data)
        self.assertEqual(git(self.remote, "show", f"docs/brain:{rel}"), (clone / rel).read_text().strip())
        self.assertEqual(data["promotion"], PR["html_url"])
        self.assertIn("head=docs/brain", self.gh_log.read_text())


if __name__ == "__main__":
    unittest.main()
