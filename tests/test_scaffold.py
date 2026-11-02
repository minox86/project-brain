import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run_cli


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)

    def scaffold(self):
        return run_cli("scaffold", "--repo", self.repo, "--product", "Fatture Pro")

    def test_scaffold_creates_layout(self):
        code, data, err = self.scaffold()
        self.assertEqual(code, 0, err)
        brain = self.repo / "brain"
        for rel in ("schema/VERSION", "schema/types/decision.md", "schema/proposals.md", "functional/features/.gitkeep",
                    "technical/environments/.gitkeep", "decisions/.gitkeep", "open-questions/.gitkeep",
                    "digests/.gitkeep", "raw/.gitkeep", "README.md"):
            self.assertTrue((brain / rel).exists(), rel)
        self.assertIn("# Fatture Pro brain", (brain / "AGENTS.md").read_text())
        self.assertIn("product: Fatture Pro", (brain / "schema/brain.md").read_text())
        out = subprocess.run([sys.executable, str(brain / ".pb/toolkit/pb.py"), "version"], cwd=str(self.repo),
                             capture_output=True, text=True)
        self.assertEqual(json.loads(out.stdout)["brain"], str(brain.resolve()))
        self.assertTrue((brain / ".pb/toolkit/VERSION").read_text().strip())
        self.assertTrue((self.repo / ".github/workflows/pb-validate.yml").is_file())
        self.assertFalse((self.repo / ".github/workflows/pb-generate.yml").exists())
        merge_back = (self.repo / ".github/workflows/pb-brain-branch.yml").read_text()
        self.assertIn('branches: ["main"]', merge_back)
        self.assertIn("origin/main", merge_back)
        self.assertNotIn("{{", merge_back)
        settings = json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertTrue(settings["enabledPlugins"]["pb@project-brain"])
        claude = (self.repo / "CLAUDE.md").read_text()
        self.assertIn("<!-- pb:start -->\nFor product and domain context read brain/AGENTS.md.\n<!-- pb:end -->", claude)
        self.assertIn("brain/.pb/cache/", (self.repo / ".gitignore").read_text())
        self.assertIn("brain/AGENTS.md", data["created"])

    def test_upgrade_rewrites_workflows_of_an_existing_brain(self):
        self.scaffold()
        (self.repo / ".github/workflows/pb-generate.yml").write_text("old\n")
        (self.repo / ".github/workflows/pb-brain-branch.yml").unlink()
        agents = self.repo / "brain/AGENTS.md"
        agents.write_text(agents.read_text().replace(
            agents.read_text()[agents.read_text().index("The brain lives"):agents.read_text().index("never edit generated files")],
            "Write through the `pb` plugin skills (`/pb:put`) or, by hand, following the types. Never edit generated files"))
        code, data, err = run_cli("scaffold", "--repo", self.repo, "--upgrade")
        self.assertEqual(code, 0, err)
        self.assertFalse((self.repo / ".github/workflows/pb-generate.yml").exists())
        self.assertTrue((self.repo / ".github/workflows/pb-brain-branch.yml").is_file())
        self.assertIn("Write only through the `pb` plugin skills", agents.read_text())

    def test_scaffold_refuses_existing_brain(self):
        self.scaffold()
        code, data, _ = self.scaffold()
        self.assertEqual(code, 2)
        self.assertIn("already", data["error"])

    def test_scaffold_claude_md_idempotent_and_keeps_content(self):
        (self.repo / "CLAUDE.md").write_text("# Repo rules\n")
        (self.repo / ".github/workflows").mkdir(parents=True)
        (self.repo / ".github/workflows/pb-validate.yml").write_text("custom\n")
        code, data, _ = self.scaffold()
        self.assertEqual(code, 0)
        self.assertIn(".github/workflows/pb-validate.yml", data["skipped"])
        self.assertEqual((self.repo / ".github/workflows/pb-validate.yml").read_text(), "custom\n")
        text = (self.repo / "CLAUDE.md").read_text()
        self.assertTrue(text.startswith("# Repo rules\n"))
        from pb_core.scaffold import ensure_claude_pointer
        ensure_claude_pointer(self.repo)
        self.assertEqual((self.repo / "CLAUDE.md").read_text().count("<!-- pb:start -->"), 1)

    def test_scaffolded_brain_validates_clean(self):
        self.scaffold()
        for cmd in ("validate", "generate", "stats", "lint"):
            code, data, err = run_cli(cmd, cwd=self.repo)
            self.assertEqual(code, 0, (cmd, data, err))
        code, data, _ = run_cli("context", "--paths", "x", cwd=self.repo)
        self.assertEqual((code, data["pages"]), (0, []))

    def test_toolkit_sync_refreshes_vendored_copy(self):
        self.scaffold()
        vendored = self.repo / "brain/.pb/toolkit/pb_core/__init__.py"
        vendored.write_text("stale")
        code, _, _ = run_cli("toolkit-sync", cwd=self.repo)
        self.assertEqual(code, 0)
        self.assertIn("__version__", vendored.read_text())

    def test_toolkit_vendors_routine_instructions_with_plugin_layout(self):
        self.scaffold()
        toolkit = self.repo / "brain/.pb/toolkit"
        for rel in ("skills/sync/SKILL.md", "skills/put/SKILL.md", "skills/meeting/SKILL.md",
                    "references/conventions.md", "references/writing.md", "references/reader.md"):
            self.assertEqual((toolkit / rel).read_text(), (ROOT / rel).read_text(), rel)
        # Every BASE-relative path the sync skill uses resolves inside the vendored copy.
        base = toolkit / "skills/sync"
        text = (base / "SKILL.md").read_text()
        for rel in sorted(set(re.findall(r"BASE/([\w./-]+\.md)", text))):
            self.assertTrue((base / rel).resolve().is_file(), rel)

    def test_toolkit_sync_from_vendored_copy_refuses_and_keeps_toolkit(self):
        self.scaffold()
        vendored = self.repo / "brain/.pb/toolkit/pb.py"
        out = subprocess.run([sys.executable, str(vendored), "toolkit-sync"], cwd=str(self.repo),
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertTrue(vendored.is_file())


if __name__ == "__main__":
    unittest.main()
