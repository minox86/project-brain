"""Context packs: from a Jira key, a feature, or code paths to the relevant brain pages."""
import fnmatch
import posixpath

from . import links
from .brain import CONTEXT, _without_heading

SECTIONS = [
    ("feature", "Features"),
    ("role", "Roles"),
    ("process", "Processes"),
    ("concept", "Concepts"),
    ("module", "Modules"),
    ("contract", "Contracts"),
    ("integration", "Integrations"),
    ("decision", "Decisions"),
    ("open-question", "Open questions"),
]
_ORDER = {t: i for i, (t, _) in enumerate(SECTIONS)}
CLOSED = {"superseded", "deprecated", "retired", "repealed", "dropped", "resolved", "done", "cancelled"}
_GLOB = set("*?[")


def _clean(path):
    path = path.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def path_matches(pattern, path):
    """Does a module `paths` entry cover a repo-relative file path?"""
    pattern, path = _clean(pattern), _clean(path)
    prefix = None
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
    elif pattern.endswith("/"):
        prefix = pattern[:-1]
    elif not _GLOB & set(pattern):
        prefix = pattern
    if prefix is not None and not _GLOB & set(prefix):
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def modules_for_paths(brain, paths):
    return [m for m in brain.pages()
            if m.type == "module" and any(path_matches(str(pat), f) for pat in _list(m.get("paths")) for f in paths)]


def summary_of(page, max_words=40):
    """`summary` field, else the first prose paragraph of the body."""
    if page.get("summary"):
        return str(page.get("summary"))
    for block in page.body.split("\n\n"):
        lines = [l for l in block.strip().splitlines() if l.strip() and not l.lstrip().startswith("#")]
        if lines:
            words = " ".join(lines).split()
            return " ".join(words[:max_words]) + (" …" if len(words) > max_words else "")
    return ""


REPO_ROOT = ".."  # brain-relative: links in a pack shown in chat are valid from the repo root (`brain/…`)


def build_context(brain, jira=None, feature=None, paths=None, max_words=None, links_from=CONTEXT):
    """The pack for a seed. Its links are valid from the brain-relative folder `links_from`: `.pb/context/`, where
    generate writes packs, or REPO_ROOT for a pack shown in chat."""
    seeds = _seeds(brain, jira, feature, paths)
    collected = {p.rel: p for p in seeds}

    def add(pages):
        for p in pages:
            collected.setdefault(p.rel, p)

    for p in list(collected.values()):
        if p.type == "feature":
            add(_targets(brain, p, "modules") + _targets(brain, p, "concepts") + _targets(brain, p, "roles"))
    for m in [p for p in collected.values() if p.type == "module"]:
        for other in brain.pages():
            if other.type == "contract" and m.title in _link_titles(brain, other, ("provided_by", "consumed_by")):
                add([other])
            if other.type == "integration" and m.title in _link_titles(brain, other, ("used_by",)):
                add([other])
            if other.type == "feature" and m.title in _link_titles(brain, other, ("modules",)):
                add([other] + _targets(brain, other, "concepts"))
    hit = {p.title for p in collected.values()}
    for other in brain.pages():
        if set(_link_titles(brain, other, ("applies_to",))) & hit and other.get("status") not in CLOSED:
            add([other])  # processes and domain types (rules, regulations…) point at what they govern
        affects = set(_link_titles(brain, other, ("affects",)))
        if not affects & hit:
            continue
        if other.type == "decision" and other.get("status") != "superseded":
            add([other])
        if other.type == "open-question" and other.get("status", "open") == "open":
            add([other])

    pages = sorted(collected.values(), key=lambda p: (_ORDER.get(p.type, 99), p.type, p.title.lower()))
    limit = max_words or brain.config.get("context_pack_max_words") or 4000
    mode = {p.rel: "full" for p in pages}
    markdown = _render(brain, seeds, pages, mode, links_from)
    for p in sorted(pages, key=lambda p: -p.words):
        if _count(markdown) <= limit:
            break
        mode[p.rel] = "summary"
        markdown = _render(brain, seeds, pages, mode, links_from)
    return {
        "seeds": [p.title for p in seeds],
        "pages": [{"title": p.title, "type": p.type, "path": p.rel, "included": mode[p.rel]} for p in pages],
        "markdown": markdown,
        "words": _count(markdown),
    }


def _seeds(brain, jira, feature, paths):
    if jira:
        key = jira.strip().upper()
        return [p for p in brain.pages() if p.type == "feature" and (
            key in [str(j).upper() for j in _list(p.get("jira"))]
            or f"JIRA:{key}" in [str(s).upper() for s in _list(p.get("sources"))])]
    if feature:
        found, _ = brain.lookup(feature)
        return [found] if found is not None else []
    return modules_for_paths(brain, paths or [])


def _render(brain, seeds, pages, mode, dst):
    """The pack, its links valid from the brain-relative folder `dst`: the links of the embedded text are rebased."""
    if not pages:
        return ""
    out = [f"# Context: {', '.join(p.title for p in seeds)}", ""]
    known = {t for t, _ in SECTIONS}
    others = sorted({p.type for p in pages if p.type not in known})
    for type_, heading in SECTIONS[:3] + [(t, _plural(t)) for t in others] + SECTIONS[3:]:
        group = [p for p in pages if p.type == type_]
        if not group:
            continue
        out += [f"## {heading}", ""]
        for p in group:
            out.append(f"### {p.title}")
            here = posixpath.dirname(p.rel)
            if mode[p.rel] == "full":
                out += [links.rewrite(brain, _without_heading(p.body).strip(), here, dst), ""]
            else:
                out += [f"{links.rewrite(brain, summary_of(p), here, dst)} "
                        f"([{p.title}]({links.href(p.rel, dst)}))", ""]
    return "\n".join(out).rstrip() + "\n"


def _plural(type_):
    words = type_.replace("-", " ")
    return words[:1].upper() + words[1:] + ("" if words.endswith("s") else "s")


def _targets(brain, page, field):
    return [found for found in (brain.lookup(t)[0] for t in _link_titles_raw(page, (field,))) if found is not None]


def _link_titles(brain, page, fields):
    out = []
    for target in _link_titles_raw(page, fields):
        found, _ = brain.lookup(target)
        out.append(found.title if found is not None else target)
    return out


def _link_titles_raw(page, fields):
    out = []
    for field in fields:
        for item in _list(page.get(field)):
            if isinstance(item, str):
                out.extend(links.extract(item) if "[[" in item else [item.strip()] if item.strip() else [])
    return out


def _count(text):
    return len(text.split())


def _list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
