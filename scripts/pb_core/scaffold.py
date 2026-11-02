"""Creates brain/ in a monorepo: schema from a preset, folders, agent rules, CI, vendored toolkit."""
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__, frontmatter
from .errors import UsageError

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
POINTER = "<!-- pb:start -->\nFor product and domain context read brain/AGENTS.md.\n<!-- pb:end -->"
PROPOSALS = "# Schema proposals\n\nOne line per proposal: `- [ ] P<n> · <proposal>`.\n"
# Skills the cloud routine follows from the repo: sync, and those sync defers to (put's analysis, meeting's step 3).
ROUTINE_SKILLS = ("sync", "put", "meeting")
ROUTINE_SYNC_SKILL = "skills/sync/SKILL.md"
WORKFLOWS = ("pb-validate.yml", "pb-generate.yml", "pb-brain-branch.yml")
MARKETPLACE = {"project-brain": {"source": {"source": "github", "repo": "minox86/project-brain"}}}
PLUGIN_ID = "pb@project-brain"
NEEDS_QUOTES =re.compile(r"""^[\[\]{}#&*!|>'"%@`-]|[:#]\s|,\s""")


def scaffold(repo_root, product, preset="software-product"):
    repo = Path(repo_root).resolve()
    brain = repo / "brain"
    if (brain / "schema" / "VERSION").is_file():
        raise UsageError(f"a brain already exists in {brain}")
    preset_dir = PLUGIN_ROOT / "presets" / preset
    if not (preset_dir / "VERSION").is_file():
        raise UsageError(f"unknown preset '{preset}'")
    created, skipped = [], []

    def note(path):
        created.append(path.relative_to(repo).as_posix())

    shutil.copytree(str(preset_dir), str(brain / "schema"), dirs_exist_ok=True)
    note(brain / "schema")
    _set_product(brain / "schema" / "brain.md", product)
    (brain / "schema" / "proposals.md").write_text(PROPOSALS, encoding="utf-8")

    folders = ["digests", "raw"]
    for path in sorted((brain / "schema" / "types").glob("*.md")):
        meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        if meta and meta.get("folder"):
            folders.append(str(meta["folder"]).strip("/"))
    for folder in folders:
        keep = brain / folder / ".gitkeep"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.touch()
        note(keep)

    for name in ("AGENTS.md", "README.md"):
        text = (PLUGIN_ROOT / "templates" / "brain" / name).read_text(encoding="utf-8")
        (brain / name).write_text(text.replace("{{product}}", product), encoding="utf-8")
        note(brain / name)

    note(sync_toolkit(brain))

    default = _default_branch(repo)
    workflows = repo / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    for name in WORKFLOWS:
        target = workflows / name
        if target.exists():
            skipped.append(target.relative_to(repo).as_posix())
            continue
        text = (PLUGIN_ROOT / "templates" / "github" / name).read_text(encoding="utf-8")
        target.write_text(text.replace("{{default_branch}}", default), encoding="utf-8")
        note(target)

    if ensure_claude_pointer(repo):
        created.append("CLAUDE.md")
    if enable_plugin(repo):
        created.append(".claude/settings.json")
    gitignore = repo / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if "brain/.pb/cache/" not in existing.splitlines():
        sep = "" if not existing or existing.endswith("\n") else "\n"
        gitignore.write_text(existing + sep + "brain/.pb/cache/\n", encoding="utf-8")
    return {"brain": str(brain), "created": created, "skipped": skipped, "default_branch": default}


def sync_toolkit(brain):
    """Copy the running toolkit into brain/.pb/toolkit so CI and the cloud routine can run it.

    Cloud routines do not load plugins: besides the scripts, the instructions the routine follows
    (ROUTINE_SKILLS and the references) are copied with the plugin's layout, so the relative paths
    inside them (BASE/../../references/…, BASE/../meeting/SKILL.md) keep resolving. Returns the target dir.
    """
    target = Path(brain) / ".pb" / "toolkit"
    scripts = PLUGIN_ROOT / "scripts"
    if not (scripts / "pb_core").is_dir():
        raise UsageError("toolkit-sync must run from the plugin, not from the vendored copy in brain/.pb/toolkit")
    if target.exists():
        shutil.rmtree(str(target))
    target.mkdir(parents=True)
    shutil.copy2(str(scripts / "pb.py"), str(target / "pb.py"))
    shutil.copytree(str(scripts / "pb_core"), str(target / "pb_core"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(str(PLUGIN_ROOT / "references"), str(target / "references"))
    for name in ROUTINE_SKILLS:
        (target / "skills" / name).mkdir(parents=True)
        shutil.copy2(str(PLUGIN_ROOT / "skills" / name / "SKILL.md"), str(target / "skills" / name / "SKILL.md"))
    (target / "VERSION").write_text(__version__ + "\n", encoding="utf-8")
    return target


def ensure_claude_pointer(repo):
    """Add the brain pointer block to the repo CLAUDE.md once. Returns True when written."""
    path = Path(repo) / "CLAUDE.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "<!-- pb:start -->" in text:
        return False
    sep = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    path.write_text(text + sep + POINTER + "\n", encoding="utf-8")
    return True


def enable_plugin(repo):
    """Add the marketplace and enable the pb plugin in the repo's shared .claude/settings.json. True when changed."""
    import json
    path = Path(repo) / ".claude" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    markets = settings.setdefault("extraKnownMarketplaces", {})
    plugins = settings.setdefault("enabledPlugins", {})
    if "project-brain" in markets and plugins.get(PLUGIN_ID) is True:
        return False
    markets.setdefault("project-brain", MARKETPLACE["project-brain"])
    plugins[PLUGIN_ID] = True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return True


def _set_product(path, product):
    value = f'"{product}"' if NEEDS_QUOTES.search(product) else product
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"(?m)^product:.*$", lambda _: f"product: {value}", text, count=1), encoding="utf-8")


def _default_branch(repo):
    from .gitops import default_branch
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(repo), capture_output=True, text=True)
    return default_branch(repo) if inside.returncode == 0 else "main"
