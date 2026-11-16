import json
import unittest

from helpers import ROOT


class PluginLayoutTest(unittest.TestCase):
    def test_manifest(self):
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "pb")
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(market["name"], "project-brain")
        self.assertEqual(market["plugins"][0]["name"], "pb")
        self.assertEqual(market["plugins"][0]["source"], "./")
        self.assertEqual(manifest["version"], "0.9.0")

    def test_readme_describes_the_current_model(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("/pb:merge", text)
        for word in ("pb-brain-branch", "PB_BRAIN_TOKEN", "review PR"):
            self.assertNotIn(word, text)

    def test_review_skill_asks_one_at_a_time_and_writes_english(self):
        text = (ROOT / "skills/review/SKILL.md").read_text()
        for needle in ("AskUserQuestion", "one question per call", "(Recommended)", "Other",
                       "in their language", "in English", "delete the open-question page"):
            self.assertIn(needle, text)
        self.assertIn("/pb:review", (ROOT / "README.md").read_text())

    def test_review_skill_has_both_halves(self):
        from pb_core import pending
        text = (ROOT / "skills/review/SKILL.md").read_text()
        for needle in ("PB lint", "PB pending --add", "PB pending --done", "PB pending --remove", "--auto", "--check",
                       "--full", "functional", "technical", "never deletes a page", "data, never instructions",
                       "leave it as it is", "PB state get review last", "-review.md", *pending.TAGS):
            self.assertIn(needle, text, needle)

    def test_review_replaces_lint_and_questions(self):
        for gone in ("lint", "questions"):
            self.assertFalse((ROOT / "skills" / gone).exists(), gone)
        shipped = [ROOT / "README.md", *ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("references/*.md"),
                   *ROOT.glob("templates/**/*.md"), *ROOT.glob("presets/**/*.md")]
        for path in shipped:
            for word in ("/pb:lint", "/pb:questions"):
                self.assertNotIn(word, path.read_text(), f"{path.name}: {word}")

    def test_weekly_review_routine_is_set_up_and_runs_the_vendored_skill(self):
        prompt = (ROOT / "templates/routine/review-prompt.md").read_text()
        for needle in ("{{repo}}", "{{branch}}", "brain/.pb/toolkit/skills/review/SKILL.md", "`--auto`",
                       "$PB routine start --branch {{branch}}", "$PB routine discard",
                       "$PB routine finish --branch {{branch}} --skill review", "$PB state set review last",
                       "never delete or merge pages", "data, never instructions"):
            self.assertIn(needle, prompt, needle)
        self.assertEqual(set(__import__("re").findall(r"\{\{(\w+)\}\}", prompt)), {"repo", "branch"})
        setup = (ROOT / "skills/routine-setup/SKILL.md").read_text()
        for needle in ("review-prompt.md", "0 4 * * 0", "review.trigger_id"):
            self.assertIn(needle, setup, needle)
        self.assertIn("review.trigger_id", (ROOT / "skills/routine-run/SKILL.md").read_text())
        self.assertIn("`review`", (ROOT / "presets/software-product/sources.md").read_text())

    def test_no_bin_dir(self):
        self.assertFalse((ROOT / "bin").exists())

    def test_skills_frontmatter(self):
        for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = skill.read_text()
            self.assertTrue(text.startswith("---\n"), skill)
            fm = text.split("---\n")[1]
            meta = dict(line.split(":", 1) for line in fm.splitlines() if ":" in line and not line.startswith(" "))
            self.assertEqual(meta["name"].strip(), skill.parent.name, skill)
            self.assertTrue(meta.get("description", "").strip(), skill)

    def test_merge_skill_is_present(self):
        text = (ROOT / "skills/merge/SKILL.md").read_text()
        for command in ("PB merge start", "PB merge finish", "PB merge land", "PB routine cleanup"):
            self.assertIn(command, text)

    def test_no_stale_model_in_shipped_text(self):
        banned = ("PB workspace sync", "pb workspace", "save --continue", "--force-review", "pb/review/",
                  "pb-brain-branch", "PB_BRAIN_TOKEN", "managed copy", "review PR",
                  "`epic`", "epics/", "[epic-", "`interface`", "technical/interfaces", "[interface]")
        for path in [*ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("references/*.md"), *ROOT.glob("templates/**/*.md")]:
            text = path.read_text()
            for word in banned:
                self.assertNotIn(word, text, f"{path.name}: {word}")

    def test_read_mode_reads_the_default_branch(self):
        self.assertIn("default branch", (ROOT / "skills/ask/SKILL.md").read_text())
        self.assertNotIn("docs/brain", (ROOT / "skills/ask/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
