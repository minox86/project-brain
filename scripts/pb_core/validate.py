"""Checks pages against the schema; scans every brain text for secrets."""
import difflib
import os
import re
from pathlib import Path

from . import frontmatter, links, policy
from .brain import _as_list
from .changes import changed_pages
from .errors import FrontmatterError
from .scaffold import ROUTINE_SYNC_SKILL
from .secrets import scan

IMPLICIT = {"type", "title", "aliases", "summary", "created", "updated", "sources", "archived"}
BAD_TITLE = re.compile(r'[\\/:*?"<>|#^\[\]]')
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")

# Noise checks: warnings on the pages a change creates or updates (against a git base).
NOISE = ("possible-duplicate", "new-orphan", "missing-source", "log-heading", "ephemeral", "verbatim")
LOG_HEADING = re.compile(r"^#{1,6}\s.*(\d{4}-\d{2}-\d{2}|\b(updates?|changelog|history|aggiornament[oi]|storico)\b)",
                         re.IGNORECASE)
EPHEMERAL = re.compile(r"\b((this|next|last) (sprint|week)|today|yesterday|tomorrow|wip|todo"
                       r"|(questo|prossimo|scorso) sprint|(questa|prossima|scorsa) settimana|oggi|ieri|domani)\b",
                       re.IGNORECASE)
VERBATIM_WORDS = 40
DUPLICATE_RATIO = 0.85


def validate(brain, paths=None, base="HEAD"):
    errors, warnings = [], []
    scope = _scope(brain, paths)
    for rel in sorted(scope or ()):
        if not (brain.root / rel).exists():
            errors.append({"path": rel, "code": "unknown-path", "message": f"{rel} is not in the brain at {brain.root}"})

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

    changed = changed_pages(brain, base) if base else None
    for p, code, message in noise(brain, changed):
        report(warnings, p.rel, code, message)

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
    if isinstance(routine, dict) and routine.get("branch") \
            and not (brain.root / ".pb" / "toolkit" / ROUTINE_SYNC_SKILL).is_file():
        report(warnings, "schema/sources.md", "routine-instructions-missing",
               "the cloud routine reads its instructions from brain/.pb/toolkit, which has none: "
               "run `PB toolkit-sync` from the plugin and commit it to the routine's branch")

    for problem in policy.problems(brain):
        report(errors, "schema/review.md", "bad-review-policy", problem)

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
            if name == "archived" and value is not None and not isinstance(value, bool):
                error("bad-kind", "'archived' must be true or false")
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


def noise(brain, changed):
    """[(page, code, message)] for the created or updated pages in `changed` (see changes.changed_pages)."""
    if not changed:
        return []
    pages = [p for p in brain.pages() if p.type in brain.types]
    touched = [p for p in pages if p.rel in changed and changed[p.rel]["change"] != "delete"]
    incoming = {}
    for p in pages:
        for t in page_targets(brain, p):
            if t.rel != p.rel:
                incoming.setdefault(t.rel, set()).add(p.rel)
    out = []
    for p in touched:
        if changed[p.rel]["change"] == "create":
            for other in pages:
                if other is not p and looks_duplicate(p, other):
                    out.append((p, "possible-duplicate",
                                f"looks like [[{other.title}]]: update that page instead, or make the titles distinct"))
                    break
            if not incoming.get(p.rel):
                out.append((p, "new-orphan", "new page that no other page links: link it from the page it belongs to"))
        if not _as_list(p.get("sources")):
            out.append((p, "missing-source", "'sources' is empty: cite where this knowledge comes from"))
        out += [(p, code, message) for code, message in _body_noise(p.body)]
    return out


def _body_noise(body):
    found, quote, quote_line, fenced = {}, 0, 0, False
    for n, line in enumerate(body.splitlines() + [""], 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith(">"):
            quote_line = quote_line or n
            quote += len(line.lstrip("> ").split())
            continue
        if quote > VERBATIM_WORDS and "verbatim" not in found:
            found["verbatim"] = f"line {quote_line}: a {quote}-word quote: summarise it and link the source"
        quote, quote_line = 0, 0
        if LOG_HEADING.match(line) and "log-heading" not in found:
            found["log-heading"] = (f"line {n}: '{line.strip()}' reads like a log entry: "
                                    "consolidate into the page instead of dated or update sections")
        hit = EPHEMERAL.search(line)
        if hit and not line.startswith("#") and "ephemeral" not in found:
            found["ephemeral"] = (f"line {n}: '{hit.group(0)}' is status, not durable knowledge: "
                                  "state the lasting fact or drop it")
    return list(found.items())


def looks_duplicate(a, b):
    if a.type != b.type:
        return False
    names_a = {a.title.lower()} | {str(x).lower() for x in _as_list(a.get("aliases"))}
    names_b = {b.title.lower()} | {str(x).lower() for x in _as_list(b.get("aliases"))}
    ratio = difflib.SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
    return ratio >= DUPLICATE_RATIO or bool(names_a & names_b)


def page_targets(brain, page, skip_fields=()):
    """Distinct pages that `page` links to, from its body and its link fields."""
    names = links.extract(page.body) + [t for field, t in links.meta_links(page.meta, brain.types.get(page.type))
                                        if field not in skip_fields]
    unique = {}
    for name in names:
        found, _ = brain.lookup(name)
        if found is not None:
            unique[found.rel] = found
    return list(unique.values())


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
    return {brain_rel(brain, raw) for raw in paths}


def brain_rel(brain, raw):
    """A path given on the command line (absolute, or relative to the cwd or to brain/) as brain-relative."""
    path = Path(raw)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    try:
        return path.resolve().relative_to(brain.root).as_posix()
    except ValueError:
        rel = Path(raw).as_posix()
        # brain/<path> typed from the user's checkout, where the brain is the managed copy.
        return rel[len("brain/"):] if rel.startswith("brain/") else rel
