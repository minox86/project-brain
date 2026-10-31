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
NEEDS_QUOTES = re.compile(r"""^[\[\]{}#&*!|>'"%@`-]|[:#]\s|,\s""")


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
    for name in ("pb-validate.yml", "pb-generate.yml"):
        target = workflows / name
        if target.exists():
            skipped.append(target.relative_to(repo).as_posix())
            continue
        text = (PLUGIN_ROOT / "templates" / "github" / name).read_text(encoding="utf-8")
        target.write_text(text.replace("{{default_branch}}", default), encoding="utf-8")
        note(target)

    if ensure_claude_pointer(repo):
        created.append("CLAUDE.md")
    gitignore = repo / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if "brain/.pb/cache/" not in existing.splitlines():
        sep = "" if not existing or existing.endswith("\n") else "\n"
        gitignore.write_text(existing + sep + "brain/.pb/cache/\n", encoding="utf-8")
    return {"brain": str(brain), "created": created, "skipped": skipped}


def sync_toolkit(brain):
    """Copy the running toolkit into brain/.pb/toolkit so CI can run it. Returns the target dir."""
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


def _set_product(path, product):
    value = f'"{product}"' if NEEDS_QUOTES.search(product) else product
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"(?m)^product:.*$", lambda _: f"product: {value}", text, count=1), encoding="utf-8")


def _default_branch(repo):
    for args in (["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], ["branch", "--show-current"]):
        proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().rsplit("/", 1)[-1] if args[0] == "symbolic-ref" else proc.stdout.strip()
    return "main"
