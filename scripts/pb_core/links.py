"""Wikilink extraction from bodies and frontmatter."""
import re

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FREE_LINK_FIELDS = ("affects", "resolves", "resolved_by")


def extract(text):
    """Targets of every [[wikilink]] in text, stripped, in order."""
    return [m.group(1).strip() for m in WIKILINK.finditer(text or "")]


def _strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def meta_links(meta, typedef):
    """[(field, target)] for link fields of the type and free link fields."""
    out = []
    fields = typedef.fields if typedef else {}
    for name, value in (meta or {}).items():
        spec = fields.get(name) or {}
        is_link = spec.get("kind") == "link" or (spec.get("kind") == "list" and spec.get("of") == "link")
        if not is_link and name not in FREE_LINK_FIELDS:
            continue
        for item in _strings(value):
            for target in extract(item):
                out.append((name, target))
    return out
