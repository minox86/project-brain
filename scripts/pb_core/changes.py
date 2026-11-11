"""Brain pages changed against a git base: what a run or a PR creates, updates or deletes."""
import subprocess
from pathlib import Path

from . import frontmatter
from .errors import FrontmatterError


def _git(cwd, *args):
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    except FileNotFoundError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def changed_pages(brain, base="HEAD"):
    """{brain-relative path: {"change": create|update|delete, "old": meta on base or None, "old_body": body on base
    or None}} for page files.

    Compares `base` with the working tree, untracked files included. None when git or the base is unavailable.
    """
    top = _git(brain.root, "rev-parse", "--show-toplevel")
    if top is None or _git(brain.root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}") is None:
        return None
    repo = Path(top.strip()).resolve()
    prefix = brain.root.resolve().relative_to(repo).as_posix()
    diff = _git(repo, "-c", "core.quotePath=false", "diff", "--name-status", "--no-renames", "-z", base, "--", prefix)
    untracked = _git(repo, "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard", "-z",
                     "--", prefix)
    if diff is None or untracked is None:
        return None
    fields = [f for f in diff.split("\0") if f]
    entries = list(zip(fields[0::2], fields[1::2])) + [("A", f) for f in untracked.split("\0") if f]
    folders = [t.folder for t in brain.types.values() if t.folder]
    out = {}
    for status, path in entries:
        rel = path[len(prefix) + 1:] if prefix else path
        if not rel.endswith(".md") or rel.split("/")[-1] == "README.md" \
                or not any(rel.startswith(f + "/") for f in folders):
            continue
        change = {"A": "create", "D": "delete"}.get(status[0], "update")
        old, body = (None, None) if change == "create" else _meta_at(repo, base, path)
        out[rel] = {"change": change, "old": old, "old_body": body}
    return out


def _meta_at(repo, base, path):
    text = _git(repo, "show", f"{base}:{path}")
    if text is None:
        return {}, None
    try:
        meta, body = frontmatter.parse(text)
    except FrontmatterError:
        return {}, None
    return meta or {}, body
