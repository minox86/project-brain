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


if __name__ == "__main__":
    unittest.main()
