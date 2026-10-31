"""Context packs: from a Jira key, a feature or code paths to the relevant brain pages."""
import fnmatch

from . import links

SECTIONS = [
    ("feature", "Features"),
    ("concept", "Concepts"),
    ("module", "Modules"),
    ("interface", "Interfaces"),
    ("decision", "Decisions"),
    ("open-question", "Open questions"),
]
_ORDER = {t: i for i, (t, _) in enumerate(SECTIONS)}
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


def build_context(brain, jira=None, feature=None, paths=None, max_words=None):
    seeds = _seeds(brain, jira, feature, paths)
    collected = {p.rel: p for p in seeds}

    def add(pages):
        for p in pages:
            collected.setdefault(p.rel, p)

    for p in list(collected.values()):
        if p.type == "feature":
            add(_targets(brain, p, "modules") + _targets(brain, p, "concepts"))
    for m in [p for p in collected.values() if p.type == "module"]:
        add(_targets(brain, m, "interfaces"))
        for other in brain.pages():
            if other.type == "interface" and m.title in _link_titles(brain, other, ("provided_by", "consumed_by")):
                add([other])
            if other.type == "feature" and m.title in _link_titles(brain, other, ("modules",)):
                add([other])
    hit = {p.title for p in collected.values()}
    for other in brain.pages():
        affects = set(_link_titles(brain, other, ("affects",)))
        if not affects & hit:
            continue
        if other.type == "decision" and other.get("status") != "superseded":
            add([other])
        if other.type == "open-question" and other.get("status", "open") == "open":
            add([other])

    pages = sorted(collected.values(), key=lambda p: (_ORDER.get(p.type, 99), p.title.lower()))
    limit = max_words or brain.config.get("context_pack_max_words") or 4000
    mode = {p.rel: "full" for p in pages}
    markdown = _render(seeds, pages, mode)
    for p in sorted(pages, key=lambda p: -p.words):
        if _count(markdown) <= limit:
            break
        mode[p.rel] = "summary"
        markdown = _render(seeds, pages, mode)
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


def _render(seeds, pages, mode):
    if not pages:
        return ""
    out = [f"# Context: {', '.join(p.title for p in seeds)}", ""]
    for type_, heading in SECTIONS:
        group = [p for p in pages if p.type == type_]
        if not group:
            continue
        out += [f"## {heading}", ""]
        for p in group:
            out.append(f"### {p.title}")
            if mode[p.rel] == "full":
                out += [p.body.strip(), ""]
            else:
                out += [f"{summary_of(p)} (see brain/{p.rel})", ""]
    return "\n".join(out).rstrip() + "\n"


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
                out.extend(links.extract(item))
    return out


def _count(text):
    return len(text.split())


def _list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
