"""Retention: flag old closed pages as archived and delete old digests. Run by the routine, never by generate."""
import datetime
import re

from .generate import CLOSED, is_archived

DIGEST = re.compile(r"(\d{4}-\d{2}-\d{2})\.md$")


def apply_retention(brain, today):
    archived, deleted = [], []
    limit = brain.config.get("archive_after_days") or 90
    for p in brain.pages():
        if p.type not in brain.types or is_archived(p) or p.get("status") not in CLOSED.get(p.type, ()):
            continue
        try:
            updated = datetime.date.fromisoformat(str(p.get("updated")))
        except ValueError:
            continue
        if (today - updated).days > limit and _flag(p.path):
            archived.append(p.rel)

    keep = brain.config.get("digest_retention_days") or 30
    digests = brain.root / "digests"
    for path in sorted(digests.glob("*.md")) if digests.is_dir() else []:
        match = DIGEST.match(path.name)
        if not match:
            continue
        try:
            day = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if (today - day).days > keep:
            path.unlink()
            deleted.append(f"digests/{path.name}")
    return {"archived": sorted(archived), "deleted": deleted}


def _flag(path):
    """Insert `archived: true` before the closing `---` of the frontmatter, touching nothing else."""
    text = path.read_bytes().decode("utf-8")
    lines = text.split("\n")
    start = 1 if lines and lines[0].lstrip("﻿").rstrip() == "---" else None
    if start is None:
        return False
    for i in range(start, len(lines)):
        if lines[i].rstrip() == "---":
            eol = "\r" if lines[i].endswith("\r") else ""
            lines.insert(i, "archived: true" + eol)
            path.write_bytes("\n".join(lines).encode("utf-8"))
            return True
    return False
