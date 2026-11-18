"""Which sources the routine reads: the configured ones of sources.md, minus those switched off in its `disabled`
list. A switch is a whole source (`jira`) or one of its entries (`teams/<id>`); the configuration and the cursors
of what is off stay, so switching it on again resumes from where it stopped."""
import re

from . import frontmatter
from .brain import SCHEMA
from .errors import UsageError

SOURCES = ("teams", "confluence", "github", "jira", "meetings", "questions")
LISTS = ("teams", "confluence", "jira", "meetings")
KEY = "disabled"
DISABLED_LINE = re.compile(r"^disabled\s*:")


def _switches(brain):
    value = (brain.sources or {}).get(KEY)
    return [str(v) for v in value] if isinstance(value, list) else []


def _entries(brain, source):
    value = (brain.sources or {}).get(source)
    if source not in LISTS or not isinstance(value, list):
        return []
    return [str(e["id"]) for e in value if isinstance(e, dict) and e.get("id") is not None]


def _known(brain, name):
    """Why `name` cannot be switched, or None."""
    source, _, entry = name.partition("/")
    if source not in SOURCES:
        return f"unknown source '{source}', use {list(SOURCES)}"
    if entry and source not in LISTS:
        return f"'{name}': {source} has no entries, switch `{source}`"
    if entry and entry not in _entries(brain, source):
        return f"'{name}': no `{source}` entry with id '{entry}'" + \
               (f", use {_entries(brain, source)}" if _entries(brain, source) else "")
    return None


def problems(brain):
    """Why the `disabled` setting is unusable, one message each."""
    value = (brain.sources or {}).get(KEY)
    if value in (None, []):
        return []
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        return [f"disabled must be a list of sources ({', '.join(SOURCES)}) or of `<source>/<id>` entries"]
    return [f"disabled: {problem}" for problem in (_known(brain, name) for name in value) if problem]


def status(brain):
    """What a sync reads: `active` sources (with the entries to read), those switched `off`, those not configured."""
    switches = _switches(brain)
    out = {"active": [], "off": [], "unconfigured": [], "entries": {}, "disabled": switches}
    for source in SOURCES:
        value = (brain.sources or {}).get(source)
        if not value:
            out["unconfigured"].append(source)
            continue
        if source in switches:
            out["off"].append(source)
            continue
        if source in LISTS:
            ids = _entries(brain, source)
            on = [i for i in ids if f"{source}/{i}" not in switches]
            out["off"] += [f"{source}/{i}" for i in ids if i not in on]
            if not on:
                continue
            out["entries"][source] = on
        out["active"].append(source)
    return out


def switch(brain, names, on):
    """Switch sources or entries off or on, rewriting only the `disabled` line of sources.md."""
    if not names:
        raise UsageError("usage: pb sources off|on <source | source/id>…")
    bad = [problem for problem in (_known(brain, name) for name in names) if problem]
    if bad:
        raise UsageError("; ".join(bad))
    switches = _switches(brain)
    for name in names:
        if on:
            # Switching a whole source on also clears the switches of its entries.
            switches = [s for s in switches if s != name and ("/" in name or not s.startswith(name + "/"))]
        elif name not in switches:
            switches.append(name)
    _write(brain, switches)
    brain.sources[KEY] = switches
    return dict(status(brain), changed=list(names))


def _write(brain, switches):
    path = brain.schema / "sources.md"
    if not path.is_file():
        raise UsageError(f"{SCHEMA}/sources.md is missing: run `/pb:routine-setup`")
    src, body = frontmatter.split(path.read_text(encoding="utf-8"))
    kept, lines, i = [], (src or "").split("\n"), 0
    while i < len(lines):
        if DISABLED_LINE.match(lines[i]):
            i += 1
            while i < len(lines) and lines[i].strip() and (lines[i][0] in " \t-"):
                i += 1  # the items of a block list
            continue
        kept.append(lines[i])
        i += 1
    while kept and not kept[-1].strip():
        kept.pop()
    kept.append(f"{KEY}: [{', '.join(switches)}]")
    path.write_text("---\n" + "\n".join(kept) + "\n---\n" + body, encoding="utf-8")
