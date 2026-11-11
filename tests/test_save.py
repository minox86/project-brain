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
        self.assertIn("brain/README.md", out["files"])
        self.assertIn(rel, out["files"])
        self.assertTrue((self.repo / "brain/README.md").is_file())
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
        self.assertFalse((self.repo / "brain/README.md").exists())
        self.assertNotIn("brain/README.md", out["files"])

    def test_secret_in_page_blocks(self):
        self.write("brain/.pb/raw/2026/11/creds.txt", "password=hunter2hunter2hunter2\n")
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertFalse(out["saved"])
        self.assertEqual(out["errors"][0]["code"], "secret")
        self.assertEqual(out["errors"][0]["path"], "brain/.pb/raw/2026/11/creds.txt")

    def test_save_normalises_the_pages_it_handles(self):
        self.put("module", "Billing", f"paths: [a/**]\n{SRC}")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "module")
        other = self.put("concept", "Other", f"term_en: Other\n{SRC}", "See [[Billing]].\n")
        rel = self.put("feature", "Approvals", SRC, "Built in [[Billing|the billing module]].\n")
        code, out, err = self.save(rel)
        self.assertEqual(code, 0, err)
        self.assertEqual(out["normalised"], [rel])
        self.assertTrue((self.repo / rel).read_text().endswith(
            "---\n# Approvals\n\nBuilt in [the billing module](../../technical/modules/Billing.md).\n"))
        self.assertIn("See [[Billing]].", (self.repo / other).read_text())  # not in this save
        self.assertIn("[Approvals](Approvals.md)", (self.repo / "brain/functional/features/README.md").read_text())

    def test_rename_with_alias_repairs_links_in_untouched_pages(self):
        old = self.put("concept", "Association fact", f"term_en: Association fact\n{SRC}")
        user = self.put("feature", "Approval", SRC, "# Approval\n\nSee [the fact](../concepts/Association%20fact.md).\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pages")
        (self.repo / old).unlink()
        new = self.put("concept", "Association record", f"term_en: Association record\naliases: [Association fact]\n{SRC}")
        code, out, err = self.save(new, old)
        self.assertEqual(code, 0, (out, err))
        self.assertIn(user, out["files"])
        self.assertIn(user, out["normalised"])
        self.assertIn("See [the fact](../concepts/Association%20record.md).", (self.repo / user).read_text())

    def test_page_with_a_non_ascii_title(self):
        rel = self.put("concept", "Società (S.r.l.)", f"term_en: Company\n{SRC}")
        self.put("feature", "Approval", SRC, "By a [[Società (S.r.l.)]].\n")
        code, out, err = self.save()
        self.assertEqual(code, 0, (out, err))
        self.assertIn(rel, out["files"])
        self.assertIn("[Società (S.r.l.)](../concepts/Societ%C3%A0%20%28S.r.l.%29.md)",
                      (self.repo / "brain/functional/features/Approval.md").read_text())
        code, data, _ = run_cli("validate", rel, cwd=self.repo)
        self.assertEqual(code, 0, data)

    def test_readme_written_as_a_page_blocks(self):
        self.write("brain/functional/features/README.md", "---\ntype: feature\ntitle: README\n---\nx\n")
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual([(e["path"], e["code"]) for e in out["errors"]],
                         [("functional/features/README.md", "reserved-title")])

    def test_deleted_page_still_linked_with_a_markdown_link_blocks(self):
        target = self.put("concept", "Target", f"term_en: Target\n{SRC}")
        self.put("concept", "User", f"term_en: User\n{SRC}", "# User\n\nSee [the target](Target.md).\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pages")
        (self.repo / target).unlink()
        code, out, _ = self.save()
        self.assertEqual(code, 1)
        self.assertEqual([(e["code"], e["target"]) for e in out["errors"]], [("broken-link", "Target")])
        self.assertIn("the page was deleted by this save: fix the link or keep the page", out["errors"][0]["message"])

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
        self.write("brain/.pb/schema/review.md", "---\nreviewers: {technical: [\"@dev-lead\", \"acme/backend\"]}\n"
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
        self.write("brain/.pb/schema/brain.md", (self.repo / "brain/.pb/schema/brain.md").read_text() + "\nMore.\n")
        code, out, err = self.save()
        self.assertEqual(code, 0, err)
        self.assertEqual(out["watched"], [{"path": ".pb/schema/brain.md",
                                           "reason": "configuration or toolkit change: always reviewed"}])


if __name__ == "__main__":
    unittest.main()
