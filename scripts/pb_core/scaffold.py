"""Creates brain/ in a monorepo: schema from a preset, folders, agent rules, CI, vendored toolkit."""
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .brain import DIGESTS, MARKER, OLD_FORMAT, RAW, SCHEMA, Brain, is_old_format
from .errors import UsageError

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
POINTER = "<!-- pb:start -->\nFor product and domain context read brain/AGENTS.md.\n<!-- pb:end -->"
PROPOSALS = "# Schema proposals\n\nOne line per proposal: `- [ ] P<n> · <proposal>`.\n"
# Skills the cloud routine follows from the repo: sync, and those sync defers to (put's analysis, meeting's step 3).
ROUTINE_SKILLS = ("sync", "put", "meeting")
ROUTINE_SYNC_SKILL = "skills/sync/SKILL.md"
WORKFLOWS = ("pb-validate.yml",)
# pb-generate: the generated files are committed with the pages. pb-brain-branch: nothing merges the default branch back any more.
RETIRED_WORKFLOWS = ("pb-generate.yml", "pb-brain-branch.yml")
# `README.md` (no slash) covers the index and every type folder's README.md.
GITATTRIBUTES = "".join(f"{path} linguist-generated\n" for path in (
    "README.md", ".pb/context/**", ".pb/backlinks.json"))
MARKETPLACE = {"project-brain": {"source": {"source": "github", "repo": "minox86/project-brain"}}}
PLUGIN_ID = "pb@project-brain"
NEEDS_QUOTES = re.compile(r"""^[\[\]{}#&*!|>'"%@`-]|[:#]\s|\s#|,\s""")


def upgrade(repo_root):
    """An existing brain gets the current workflows (overwritten), .gitattributes, plugin settings and toolkit."""
    repo = Path(repo_root).resolve()
    brain = repo / "brain"
    _refuse_old_format(brain)
    if not (brain / MARKER).is_file():
        raise UsageError(f"no brain in {brain} to upgrade")
    created = [sync_toolkit(brain).relative_to(repo).as_posix()]
    default = _default_branch(repo)
    created += _write_workflows(repo, default, overwrite=True)[0]
    created.append(_write_gitattributes(brain).relative_to(repo).as_posix())
    deleted = []
    for name in RETIRED_WORKFLOWS:
        old = repo / ".github" / "workflows" / name
        if old.is_file():
            old.unlink()
            deleted.append(old.relative_to(repo).as_posix())
    _refresh_agents(brain)
    if enable_plugin(repo):
        created.append(".claude/settings.json")
    return {"brain": str(brain), "created": created, "deleted": deleted, "skipped": [],
            "default_branch": default}


# How the writing rule of brain/AGENTS.md began before 0.5: pre-0.4 ("Write through…") and 0.4 (the brain on
# docs/brain, "Write only through…", "Never edit `brain/` in a code branch").
AGENTS_OLD = ("Write through the `pb` plugin skills", "Write only through the `pb` plugin skills",
              "The brain lives on the branch `docs/brain`")
AGENTS_NEXT = "Content enters only if it is:"


def _refresh_agents(brain):
    """Older AGENTS.md told agents to write brain/ elsewhere or not at all: put the current writing rule in place."""
    path = brain / "AGENTS.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    template = (PLUGIN_ROOT / "templates" / "brain" / "AGENTS.md").read_text(encoding="utf-8")
    start = template.index("The brain in this checkout is the brain of your branch")
    new = template[start:template.index("\n", start)]
    old = [text.find(marker) for marker in AGENTS_OLD if marker in text]
    if not old:
        return
    first = min(old)
    first = text.rfind("\n", 0, first) + 1  # from the start of its line
    end = text.find(AGENTS_NEXT, first)
    if end < 0:  # no list after it: only the paragraphs that start with an old form go
        paragraphs = text[first:].split("\n\n")
        rest = [p for p in paragraphs if not p.startswith(AGENTS_OLD)]
        path.write_text(text[:first] + "\n\n".join([new] + rest), encoding="utf-8")
        return
    path.write_text(text[:first] + new + "\n\n" + text[end:], encoding="utf-8")


def _refuse_old_format(brain):
    if is_old_format(brain):
        raise UsageError(OLD_FORMAT, {"code": "old-format", "error": OLD_FORMAT})


def _write_gitattributes(brain):
    path = brain / ".gitattributes"
    path.write_text(GITATTRIBUTES, encoding="utf-8")
    return path


def _write_workflows(repo, default, overwrite=False):
    created, skipped = [], []
    workflows = repo / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    for name in WORKFLOWS:
        target = workflows / name
        rel = target.relative_to(repo).as_posix()
        if target.exists() and not overwrite:
            skipped.append(rel)
            continue
        text = (PLUGIN_ROOT / "templates" / "github" / name).read_text(encoding="utf-8")
        target.write_text(text.replace("{{default_branch}}", default), encoding="utf-8")
        created.append(rel)
    return created, skipped


def scaffold(repo_root, product, preset="software-product"):
    repo = Path(repo_root).resolve()
    brain = repo / "brain"
    _refuse_old_format(brain)
    if (brain / MARKER).is_file():
        raise UsageError(f"a brain already exists in {brain}: an existing brain is upgraded with --upgrade")
    preset_dir = PLUGIN_ROOT / "presets" / preset
    if not (preset_dir / "VERSION").is_file():
        raise UsageError(f"unknown preset '{preset}'")
    created, skipped = [], []

    def note(path):
        created.append(path.relative_to(repo).as_posix())

    schema = brain / SCHEMA
    shutil.copytree(str(preset_dir), str(schema), dirs_exist_ok=True)
    note(schema)
    _set_product(schema / "brain.md", product)
    (schema / "proposals.md").write_text(PROPOSALS, encoding="utf-8")

    # Type folders get their generated README.md below; only these would otherwise be empty.
    for folder in (DIGESTS, RAW):
        keep = brain / folder / ".gitkeep"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.touch()
        note(keep)

    text = (PLUGIN_ROOT / "templates" / "brain" / "AGENTS.md").read_text(encoding="utf-8")
    (brain / "AGENTS.md").write_text(text.replace("{{product}}", product), encoding="utf-8")
    note(brain / "AGENTS.md")

    note(sync_toolkit(brain))
    note(_write_gitattributes(brain))
    from .generate import generate
    created += [f"brain/{rel}" for rel in generate(Brain(brain))["written"]]

    default = _default_branch(repo)
    written, skipped = _write_workflows(repo, default)
    created += written

    if ensure_claude_pointer(repo):
        created.append("CLAUDE.md")
    if enable_plugin(repo):
        created.append(".claude/settings.json")
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
    escaped = product.replace("\\", "\\\\").replace('"', '\\"')
    value = f'"{escaped}"' if NEEDS_QUOTES.search(product) or '"' in product else product
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"(?m)^product:.*$", lambda _: f"product: {value}", text, count=1), encoding="utf-8")


def _default_branch(repo):
    from .repo import default_branch
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(repo), capture_output=True, text=True)
    return default_branch(repo) if inside.returncode == 0 else "main"
