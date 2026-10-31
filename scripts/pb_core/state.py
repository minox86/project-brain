"""Sync cursors per source and the corrections log."""
import json
import os
import tempfile

from .errors import UsageError

SOURCES = ("teams", "confluence", "github", "jira", "meetings")
CORRECTIONS_HEADER = "# Corrections\n\n| Date | Page | Wrong | Right | Evidence |\n|---|---|---|---|---|\n"


def _file(brain, source):
    if source not in SOURCES:
        raise UsageError(f"unknown source '{source}': use one of {', '.join(SOURCES)}")
    return brain.root / ".pb" / "state" / f"{source}.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, str(path))


def get(brain, source, key=None):
    data = _load(_file(brain, source))
    return data if key is None else data.get(key)


def set_(brain, source, key, value):
    path = _file(brain, source)
    data = _load(path)
    data[key] = value
    _save(path, data)
    return data


def suppress(brain, source, claim):
    path = _file(brain, source)
    data = _load(path)
    claims = data.setdefault("suppressed", [])
    if claim not in claims:
        claims.append(claim)
    _save(path, data)
    return claims


def add_correction(brain, page, wrong, right, evidence, today):
    path = brain.root / ".pb" / "corrections.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(CORRECTIONS_HEADER, encoding="utf-8")
    cells = [today.isoformat(), page, wrong, right, evidence]
    row = "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row)
    return {"date": cells[0], "page": page, "wrong": wrong, "right": right, "evidence": evidence}
