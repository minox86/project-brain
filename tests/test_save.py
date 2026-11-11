import unittest

from helpers import page, run_cli
from test_gitops import GitRepoCase, git

SRC = 'sources: ["jira:FIN-1"]'


class SaveCase(GitRepoCase):
    def setUp(self):
        super().setUp()
        git(self.repo, "checkout", "-qb", "feat/x")

    def put(self, type_, title, meta="", body="Body.\n"):
        rel, text = page(type_, title, meta, body)
        self.write("brain/" + rel, text)
        return "brain/" + rel

    def save(self, *paths):
        return run_cli("save", *paths, cwd=self.repo)


class SaveTest(SaveCase):
    def test_save_validates_regenerates_and_does_not_commit(self):
        head = git(self.repo, "rev-parse", "HEAD")
        rel = self.put("feature", "Approvals")
        code, out, err = self.save(rel)
        self.assertEqual(code, 0, err)
        self.assertTrue(out["saved"])
        self.assertEqual(out["errors"], [])
        self.assertIn("brain/index.md", out["files"])
        self.assertIn(rel, out["files"])
        self.assertTrue((self.repo / "brain/index.md").is_file())
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/x")
        self.assertEqual(out["branch"], "feat/x")
        self.assertFalse(out["on_default"])
        self.assertEqual(out["watched"], [])

    def test_save_without_paths_takes_every_changed_brain_file(self):
        good = self.put("feature", "Approvals")
        bad = self.put("decision", "Single approver")  # no area: required
        self.write("apps/web/a.ts", "code\n")
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual({e["path"] for e in out["errors"]}, {"decisions/Single approver.md"})
        (self.repo / bad).unlink()
        code, out, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertIn(good, out["files"])
        self.assertNotIn("apps/web/a.ts", out["files"])

    def test_invalid_page_blocks_and_regenerates_nothing(self):
        self.put("decision", "Single approver")
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertFalse(out["saved"])
        self.assertEqual(out["errors"][0]["code"], "missing-required")
        self.assertFalse((self.repo / "brain/index.md").exists())
        self.assertNotIn("brain/index.md", out["files"])

    def test_secret_in_page_blocks(self):
        self.write("brain/raw/2026/11/creds.txt", "password=hunter2hunter2hunter2\n")
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertFalse(out["saved"])
        self.assertEqual(out["errors"][0]["code"], "secret")
        self.assertEqual(out["errors"][0]["path"], "brain/raw/2026/11/creds.txt")

    def test_deleted_page_still_linked_blocks(self):
        target = self.put("concept", "Target", f"term_en: Target\n{SRC}")
        self.put("concept", "User", f"term_en: User\n{SRC}", "See [[Target]].\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pages")
        (self.repo / target).unlink()
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual(out["errors"][0]["code"], "broken-link")
        self.assertIn("Target", out["errors"][0]["message"])

    def test_unknown_path_is_reported(self):
        code, out, _ = self.save("brain/functional/features/Nope.md")
        self.assertEqual(code, 1)
        self.assertEqual(out["errors"][0]["code"], "not-in-brain")

    def test_save_on_default_branch_is_allowed_and_flagged(self):
        git(self.repo, "checkout", "-q", "main")
        rel = self.put("feature", "Approvals")
        code, out, err = self.save(rel)
        self.assertEqual(code, 0, err)
        self.assertTrue(out["saved"])
        self.assertTrue(out["on_default"])
        self.assertEqual(out["branch"], "main")
        self.assertEqual(git(self.repo, "rev-list", "--count", "HEAD"), "1")

    def test_save_during_merge_in_progress(self):
        self.put("feature", "Theirs")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "theirs")
        git(self.repo, "checkout", "-qb", "feat/y", "main")
        self.write("apps/web/a.ts", "code\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "code")
        git(self.repo, "merge", "--no-commit", "--no-ff", "feat/x")
        self.assertTrue((self.repo / ".git/MERGE_HEAD").is_file())
        rel = self.put("feature", "Mine")
        code, out, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertTrue(out["saved"])
        self.assertIn(rel, out["files"])
        self.assertTrue((self.repo / ".git/MERGE_HEAD").is_file())

    def test_no_brain_in_checkout(self):
        git(self.repo, "rm", "-rq", "brain")
        git(self.repo, "commit", "-qm", "no brain here")
        code, out, _ = self.save()
        self.assertEqual(code, 2)
        self.assertEqual(out["code"], "no-brain")
        self.assertEqual(out["error"], "no brain/ in this checkout: bring the default branch into your branch, "
                                       "or create the brain with /pb:init")


class WatchedTest(SaveCase):
    review_policy = True

    def setUp(self):
        super().setUp()
        self.write("brain/schema/review.md", "---\nreviewers: {technical: [\"@dev-lead\", \"acme/backend\"]}\n"
                                             "watch: [{type: decision, why: \"decisions\"}]\n---\n# Review\n")
        git(self.repo, "commit", "-qam", "policy")

    def test_watched_point_is_reported_not_held(self):
        head = git(self.repo, "rev-parse", "HEAD")
        self.put("decision", "X", f"area: technical\nstatus: accepted\n{SRC}")
        code, out, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertTrue(out["saved"])
        self.assertEqual(out["watched"][0]["path"], "decisions/X.md")
        self.assertIn("decisions", out["watched"][0]["reason"])
        self.assertTrue(out["reviewers"]["users"] or out["reviewers"]["teams"])
        self.assertEqual(out["reviewers"], {"users": ["dev-lead"], "teams": ["backend"]})
        self.assertIn("`decisions/X.md`", out["markdown"])
        self.assertTrue((self.repo / "brain/decisions/X.md").is_file())
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)

    def test_schema_change_is_always_watched(self):
        self.write("brain/schema/brain.md", (self.repo / "brain/schema/brain.md").read_text() + "\nMore.\n")
        code, out, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertEqual(out["watched"], [{"path": "schema/brain.md",
                                           "reason": "configuration or toolkit change: always reviewed"}])


if __name__ == "__main__":
    unittest.main()
