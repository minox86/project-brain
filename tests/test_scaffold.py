import json
import os
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
        self.assertFalse((self.repo / ".github/workflows/pb-brain-branch.yml").exists())
        self.assertNotIn("{{default_branch}}", (self.repo / ".github/workflows/pb-validate.yml").read_text())
        attrs = (brain / ".gitattributes").read_text()
        for line in ("index.md linguist-generated", "glossary.md linguist-generated", "features.md linguist-generated",
                     "context/** linguist-generated", ".pb/backlinks.json linguist-generated"):
            self.assertIn(line, attrs)
        settings = json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertTrue(settings["enabledPlugins"]["pb@project-brain"])
        claude = (self.repo / "CLAUDE.md").read_text()
        self.assertIn("<!-- pb:start -->\nFor product and domain context read brain/AGENTS.md.\n<!-- pb:end -->", claude)
        self.assertFalse((self.repo / ".gitignore").exists() and "brain/.pb/cache/" in (self.repo / ".gitignore").read_text())
        self.assertIn("brain/AGENTS.md", data["created"])

    def test_upgrade_rewrites_workflows_of_an_existing_brain(self):
        self.scaffold()
        (self.repo / ".github/workflows/pb-generate.yml").write_text("old\n")
        (self.repo / ".github/workflows/pb-brain-branch.yml").write_text("old\n")
        (self.repo / "brain/.gitattributes").unlink()
        agents = self.repo / "brain/AGENTS.md"
        agents.write_text(agents.read_text().replace(
            agents.read_text()[agents.read_text().index("The brain in this checkout"):agents.read_text().index("Never edit generated files")],
            "Write through the `pb` plugin skills (`/pb:put`) or, by hand, following the types. "))
        code, data, err = run_cli("scaffold", "--repo", self.repo, "--upgrade")
        self.assertEqual(code, 0, err)
        self.assertFalse((self.repo / ".github/workflows/pb-generate.yml").exists())
        self.assertFalse((self.repo / ".github/workflows/pb-brain-branch.yml").exists())
        self.assertIn(".github/workflows/pb-brain-branch.yml", data["deleted"])
        self.assertIn(".github/workflows/pb-generate.yml", data["deleted"])
        self.assertIn("index.md linguist-generated", (self.repo / "brain/.gitattributes").read_text())
        self.assertIn("The brain in this checkout is the brain of your branch. Write pages here with the `pb` skills "
                      "and commit them with your code.", agents.read_text())
        self.assertNotIn("Write through the `pb` plugin skills", agents.read_text())

    def test_validate_workflow_shape(self):
        text = (ROOT / "templates/github/pb-validate.yml").read_text()
        self.assertNotIn("push:", text)
        self.assertIn("Generated files are stale: run `PB generate` and commit", text)
        self.assertIn("review:", text)
        self.assertIn("pull-requests: write", text)
        self.assertIn("brain-only:", text)
        self.assertFalse((ROOT / "templates/github/pb-brain-branch.yml").exists())

    def test_freshness_uses_the_pr_toolkit_when_the_pr_changes_the_toolkit(self):
        text = (ROOT / "templates/github/pb-validate.yml").read_text()
        step = text[text.index("name: Generated files are fresh"):text.index("  review:")]
        self.assertIn('git diff --quiet "$BASE"...HEAD -- brain/.pb/toolkit', step)
        self.assertIn(".pb-base/brain/.pb/toolkit/pb.py", step)
        self.assertLess(step.index("-- brain/.pb/toolkit"), step.rindex("toolkit=brain/.pb/toolkit/pb.py"))
        self.assertLess(step.rindex("toolkit=brain/.pb/toolkit/pb.py"), step.index("generate\n"))

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

    def test_vendored_toolkit_writes_no_bytecode_under_brain(self):
        self.scaffold()
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE")}
        # As stock CPython does: Apple's python3 redirects the cache, so put the defaults back first.
        script = str(self.repo / "brain/.pb/toolkit/pb.py")
        boot = ("import runpy, sys; sys.pycache_prefix = None; sys.dont_write_bytecode = False; "
                f"sys.argv = [{script!r}, 'version']; runpy.run_path({script!r}, run_name='__main__')")
        out = subprocess.run([sys.executable, "-c", boot], cwd=str(self.repo), capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(list((self.repo / "brain").rglob("__pycache__")), [])

    def test_validate_workflow_runs_the_toolkit_without_bytecode(self):
        text = (ROOT / "templates/github/pb-validate.yml").read_text()
        self.assertNotRegex(text, r"python3 (?!-B )")
        self.assertEqual(text.count('python3 -B "$toolkit"'), 3)

    def test_toolkit_sync_from_vendored_copy_refuses_and_keeps_toolkit(self):
        self.scaffold()
        vendored = self.repo / "brain/.pb/toolkit/pb.py"
        out = subprocess.run([sys.executable, str(vendored), "toolkit-sync"], cwd=str(self.repo),
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertTrue(vendored.is_file())


if __name__ == "__main__":
    unittest.main()
