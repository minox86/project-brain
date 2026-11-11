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
                  "pb-brain-branch", "PB_BRAIN_TOKEN", "managed copy", "review PR")
        for path in [*ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("references/*.md"), *ROOT.glob("templates/**/*.md")]:
            text = path.read_text()
            for word in banned:
                self.assertNotIn(word, text, f"{path.name}: {word}")

    def test_read_mode_reads_the_default_branch(self):
        self.assertIn("default branch", (ROOT / "skills/ask/SKILL.md").read_text())
        self.assertNotIn("docs/brain", (ROOT / "skills/ask/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
