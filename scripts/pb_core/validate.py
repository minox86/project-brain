"""Checks pages against the schema; scans every brain text for secrets."""
import os
import re
from pathlib import Path

from . import frontmatter, links
from .errors import FrontmatterError
from .secrets import scan

IMPLICIT = {"type", "title", "aliases", "summary", "created", "updated", "sources"}
BAD_TITLE = re.compile(r'[\\/:*?"<>|#^\[\]]')
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def validate(brain, paths=None):
    errors, warnings = [], []
    scope = _scope(brain, paths)

    def report(bucket, rel, code, message):
        if scope is None or rel in scope:
            bucket.append({"path": rel, "code": code, "message": message})

    brain.pages()
    for item in brain.load_errors:
        report(errors, item["path"], "frontmatter", item["error"])

    owners = {}
    for p in brain.pages():
        names = [p.title] + [str(a) for a in _as_list(p.get("aliases"))]
        for name in names:
            owners.setdefault(name.lower(), [])
            if p not in owners[name.lower()]:
                owners[name.lower()].append(p)
    for name, pages in owners.items():
        if len(pages) > 1:
            for p in pages:
                others = ", ".join(o.rel for o in pages if o is not p)
                report(errors, p.rel, "duplicate-title", f"name '{name}' is also used by {others}")

    for p in brain.pages():
        if scope is not None and p.rel not in scope:
            continue
        _check_page(brain, p, lambda c, m, bucket=errors: report(bucket, p.rel, c, m),
                    lambda c, m: report(warnings, p.rel, c, m))

    for p in brain.pages():
        for hit in scan(p.path.read_text(encoding="utf-8")):
            report(errors, p.rel, "secret", f"line {hit['line']}: looks like a {hit['kind']} secret")

    for rel, text in _other_texts(brain):
        if scope is not None and rel not in scope:
            continue
        if rel.startswith("raw/"):
            try:
                _, body = frontmatter.parse(text)
            except FrontmatterError as exc:
                report(errors, rel, "frontmatter", str(exc))
                body = text
            limit = brain.config.get("raw_max_words")
            if limit and len(body.split()) > limit:
                report(warnings, rel, "raw-too-long",
                       f"{len(body.split())} words, limit {limit}: keep a summary and the external link instead")
        for hit in scan(text):
            report(errors, rel, "secret", f"line {hit['line']}: looks like a {hit['kind']} secret")

    routine = brain.sources.get("routine")
    if isinstance(routine, dict) and routine.get("schedule") is not None:
        problem = schedule_problem(str(routine.get("schedule")))
        if problem:
            report(errors, "schema/sources.md", "bad-schedule", problem)

    errors.sort(key=lambda f: (f["path"], f["code"]))
    warnings.sort(key=lambda f: (f["path"], f["code"]))
    return {"errors": errors, "warnings": warnings}


CRON_FIELD = re.compile(r"[0-9*,/-]+$")


def schedule_problem(cron):
    """Why a routine cron expression is unusable, or None. Routines run at most once an hour."""
    fields = cron.split()
    if len(fields) != 5 or not all(CRON_FIELD.match(f) for f in fields):
        return f"'{cron}' is not a 5-field cron expression (minute hour day month weekday)"
    minute = fields[0]
    if not minute.isdigit() or int(minute) > 59:
        return f"'{cron}' runs more than once an hour: the minute field must be one number (0-59)"
    return None


def _check_page(brain, p, error, warn):
    if not p.type:
        error("missing-type", "frontmatter has no 'type'")
        return
    typedef = brain.types.get(p.type)
    if typedef is None:
        error("unknown-type", f"type '{p.type}' is not defined in schema/types")
        return
    if not p.meta.get("title"):
        error("missing-title", "frontmatter has no 'title'")
    elif p.path.stem != p.title:
        error("title-mismatch", f"file name '{p.path.stem}' differs from title '{p.title}'")
    if BAD_TITLE.search(p.title):
        error("bad-title-chars", 'titles cannot contain \\ / : * ? " < > | # ^ [ ]')
    folder = Path(p.rel).parent.as_posix()
    if folder != typedef.folder and not folder.startswith(typedef.folder + "/"):
        error("wrong-folder", f"type '{p.type}' lives in {typedef.folder}/")

    for name in typedef.required:
        if p.meta.get(name) in (None, "", []):
            error("missing-required", f"required field '{name}' is missing")
    for name, value in p.meta.items():
        if name in IMPLICIT:
            if name in ("created", "updated") and value is not None and not DATE.match(str(value)):
                error("bad-date", f"'{name}' must be YYYY-MM-DD")
            if name in ("aliases", "sources") and value is not None and not isinstance(value, list):
                error("bad-kind", f"'{name}' must be a list")
            continue
        spec = typedef.fields.get(name)
        if spec is None:
            warn("unknown-field", f"field '{name}' is not defined for type '{p.type}'")
            continue
        if value is not None:
            _check_value(name, spec, value, error)

    for field, target in [(None, t) for t in links.extract(p.body)] + links.meta_links(p.meta, typedef):
        found, how = brain.lookup(target)
        where = f"field '{field}'" if field else "body"
        if found is None:
            error("broken-link", f"[[{target}]] in {where} matches no page")
            continue
        if how == "alias":
            warn("alias-link", f"[[{target}]] in {where} is an alias of [[{found.title}]]")
        spec = typedef.fields.get(field) if field else None
        expected = spec.get("to") if spec else None
        if expected and found.type != expected:
            warn("link-type", f"field '{field}' expects a {expected}, [[{found.title}]] is a {found.type}")

    if typedef.max_words and p.words > typedef.max_words:
        warn("over-budget", f"{p.words} words, budget {typedef.max_words}: condense the page")


def _check_value(name, spec, value, error):
    kind = spec.get("kind", "string")
    if kind == "list":
        if not isinstance(value, list):
            error("bad-kind", f"'{name}' must be a list")
            return
        item_spec = {"kind": spec.get("of", "string"), "values": spec.get("values")}
        for item in value:
            _check_value(name, item_spec, item, error)
        return
    if kind == "enum" and value not in (spec.get("values") or []):
        error("bad-enum", f"'{name}' must be one of {spec.get('values')}, got '{value}'")
    elif kind == "date" and not DATE.match(str(value)):
        error("bad-date", f"'{name}' must be YYYY-MM-DD")
    elif kind == "link" and not (isinstance(value, str) and links.extract(value)):
        error("bad-kind", f"'{name}' must be a [[wikilink]]")
    elif kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        error("bad-kind", f"'{name}' must be a number")
    elif kind == "bool" and not isinstance(value, bool):
        error("bad-kind", f"'{name}' must be true or false")
    elif kind in ("string", "text") and isinstance(value, (list, dict)):
        error("bad-kind", f"'{name}' must be a single value")


def _other_texts(brain):
    """(rel, text) of non-page brain files that must be scanned: raw/, digests/, AGENTS.md."""
    root = brain.root
    candidates = [root / "AGENTS.md"]
    for folder in ("raw", "digests"):
        base = root / folder
        if base.is_dir():
            candidates.extend(sorted(base.rglob("*.md")))
    for path in candidates:
        if path.is_file():
            try:
                yield path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue


def _scope(brain, paths):
    if not paths:
        return None
    scope = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(os.getcwd()) / path
        try:
            scope.add(path.resolve().relative_to(brain.root).as_posix())
        except ValueError:
            scope.add(raw)
    return scope


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
