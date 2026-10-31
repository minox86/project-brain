"""Structural maintenance checks on top of validate."""
import datetime
import difflib
import os

from . import links
from .context import path_matches
from .generate import is_archived
from .stats import stats
from .validate import validate

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "vendor", "target", "brain", "__pycache__"}


def lint(brain, today):
    findings = []

    def add(code, page_or_rel, message, related=None):
        rel = page_or_rel if isinstance(page_or_rel, str) else page_or_rel.rel
        item = {"code": code, "path": rel, "message": message}
        if related:
            item["related"] = related
        findings.append(item)

    checked = validate(brain)
    for f in checked["errors"]:
        add(f["code"], f["path"], f["message"])
    for f in checked["warnings"]:
        if f["code"] == "over-budget":
            add(f["code"], f["path"], f["message"])

    pages = [p for p in brain.pages() if p.type in brain.types]
    outgoing = {p.rel: _targets(brain, p) for p in pages}
    incoming = {p.rel: 0 for p in pages}
    for rel, targets in outgoing.items():
        for t in targets:
            if t.rel != rel:
                incoming[t.rel] += 1

    for p in pages:
        if not incoming[p.rel] and not [t for t in outgoing[p.rel] if t.rel != p.rel]:
            add("orphan", p, "no page links here and it links nowhere: link it or remove it")
        if p.type == "open-question" and p.get("status", "open") == "open":
            age = _age(p, today)
            limit = brain.config.get("open_question_stale_days") or 30
            if age is not None and age > limit:
                add("stale-open-question", p, f"open and untouched for {age} days")
        if is_archived(brain, p, today):
            add("archivable", p, "closed long ago: it is left out of index.md; consider deleting it")

    _duplicates(pages, add)
    _dead_paths(brain, pages, add)
    _superseded_refs(brain, pages, add)
    findings.sort(key=lambda f: (f["path"], f["code"]))
    return {"findings": findings, "stats": stats(brain)}


def _targets(brain, page, skip_fields=()):
    names = links.extract(page.body) + [t for field, t in links.meta_links(page.meta, brain.types.get(page.type))
                                        if field not in skip_fields]
    found = (brain.lookup(n)[0] for n in names)
    unique = {}
    for f in found:
        if f is not None:
            unique[f.rel] = f
    return list(unique.values())


def _age(page, today):
    try:
        return (today - datetime.date.fromisoformat(str(page.get("updated")))).days
    except ValueError:
        return None


def _duplicates(pages, add):
    seen = set()
    for i, a in enumerate(pages):
        for b in pages[i + 1:]:
            if a.type != b.type or (b.rel, a.rel) in seen:
                continue
            names_a = {a.title.lower()} | {str(x).lower() for x in _as_list(a.get("aliases"))}
            names_b = {b.title.lower()} | {str(x).lower() for x in _as_list(b.get("aliases"))}
            ratio = difflib.SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
            if ratio >= 0.85 or names_a & names_b:
                seen.add((a.rel, b.rel))
                add("duplicate-candidate", a, f"looks like a duplicate of [[{b.title}]]: merge them", [b.rel])


def _dead_paths(brain, pages, add):
    modules = [p for p in pages if p.type == "module" and p.get("paths")]
    if not modules:
        return
    files = []
    for folder, dirs, names in os.walk(brain.repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(folder, brain.repo_root)
        for name in names:
            files.append(name if rel_dir == "." else f"{rel_dir}/{name}".replace(os.sep, "/"))
    for m in modules:
        patterns = m.get("paths") if isinstance(m.get("paths"), list) else [m.get("paths")]
        if not any(path_matches(str(pat), f) for pat in patterns for f in files):
            add("dead-module-paths", m, f"no file in the repo matches {patterns}: update paths or remove the module")


def _superseded_refs(brain, pages, add):
    successors = {}
    for p in pages:
        if p.type == "decision":
            for _, target in links.meta_links({"supersedes": p.get("supersedes")}, brain.types.get("decision")):
                found, _ = brain.lookup(target)
                if found is not None:
                    successors.setdefault(found.rel, []).append(p)
    for p in pages:
        targets = {t.rel: t for t in _targets(brain, p, skip_fields=("supersedes",))}
        for t in targets.values():
            if t.type != "decision" or t.get("status") != "superseded" or t.rel == p.rel:
                continue
            newer = successors.get(t.rel, [])
            if not any(n.rel in targets for n in newer):
                hint = ", ".join(f"[[{n.title}]]" for n in newer) or "its successor"
                add("superseded-referenced", p, f"links superseded [[{t.title}]]: link {hint} instead or as well")


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
