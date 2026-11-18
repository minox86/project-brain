"""Checks pages against the schema; scans every brain text for secrets."""
import difflib
import os
import re
from pathlib import Path

from . import frontmatter, links, pending, policy, questions, sources
from .brain import DIGESTS, INDEX, RAW, SCHEMA, _as_list
from .changes import changed_pages
from .errors import FrontmatterError
from .messages import format_problem
from .scaffold import ROUTINE_REVIEW_SKILL, ROUTINE_SYNC_SKILL
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

    def report(bucket, rel, code, message, **extra):
        if scope is None or rel in scope:
            bucket.append(dict({"path": rel, "code": code, "message": message}, **extra))

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
        _check_page(brain, p, lambda c, m, bucket=errors, **x: report(bucket, p.rel, c, m, **x),
                    lambda c, m: report(warnings, p.rel, c, m))
    for rel in _readme_pages(brain):
        report(errors, rel, "reserved-title", f"{INDEX} is the folder's generated index, never a page: "
                                              "give the page another title")

    changed = changed_pages(brain, base) if base else None
    for p, code, message in noise(brain, changed):
        report(warnings, p.rel, code, message)

    for p in brain.pages():
        for hit in scan(p.path.read_text(encoding="utf-8")):
            report(errors, p.rel, "secret", f"line {hit['line']}: looks like a {hit['kind']} secret")

    for rel, text in _other_texts(brain):
        # The queue is scanned whatever the scope: routine runs validate pages only, and its lines quote pages.
        if scope is not None and rel not in scope and rel != pending.PATH:
            continue
        if rel.startswith(RAW + "/"):
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
            errors.append({"path": rel, "code": "secret",
                           "message": f"line {hit['line']}: looks like a {hit['kind']} secret"})

    routine = brain.sources.get("routine")
    if isinstance(routine, dict) and routine.get("schedule") is not None:
        problem = schedule_problem(str(routine.get("schedule")))
        if problem:
            report(errors, f"{SCHEMA}/sources.md", "bad-schedule", problem)
    if isinstance(routine, dict) and routine.get("branch") \
            and not (brain.root / ".pb" / "toolkit" / ROUTINE_SYNC_SKILL).is_file():
        report(warnings, f"{SCHEMA}/sources.md", "routine-instructions-missing",
               "the cloud routine reads its instructions from brain/.pb/toolkit, which has none: "
               "run `PB toolkit-sync` from the plugin and commit it to the routine's branch")

    weekly = brain.sources.get("review")
    if isinstance(weekly, dict) and weekly.get("schedule") is not None:
        problem = schedule_problem(str(weekly.get("schedule"))) or weekly_problem(str(weekly.get("schedule")))
        if problem:
            report(errors, f"{SCHEMA}/sources.md", "bad-schedule", problem)
        elif not (brain.root / ".pb" / "toolkit" / ROUTINE_REVIEW_SKILL).is_file():
            report(warnings, f"{SCHEMA}/sources.md", "routine-instructions-missing",
                   "the weekly review reads its instructions from brain/.pb/toolkit, which has none: "
                   "run `PB toolkit-sync` from the plugin and commit it to the routine's branch")

    for problem in questions.problems(brain):
        report(errors, f"{SCHEMA}/sources.md", "bad-questions", problem)
    for problem in sources.problems(brain):
        report(errors, f"{SCHEMA}/sources.md", "bad-disabled", problem)
    problem = questions.language_problem(brain.config.get("team_language"))
    if problem:
        report(errors, f"{SCHEMA}/brain.md", "bad-team-language", problem)
    # Whatever the scope: the schema's settings are no place for a webhook URL or any other secret.
    for name in ("sources.md", "brain.md", "review.md"):
        path = brain.schema / name
        for hit in scan(path.read_text(encoding="utf-8")) if path.is_file() else []:
            errors.append({"path": f"{SCHEMA}/{name}", "code": "secret",
                           "message": f"line {hit['line']}: looks like a {hit['kind']} secret"})

    # Whatever the scope: CI and routine runs validate pages only, and a broken queue silently loses items.
    for bad in pending.read(brain)["bad"]:
        errors.append({"path": pending.PATH, "code": "bad-pending",
                       "message": f"line {bad['line']} is {bad['why']}: a queue line is `{pending.FORMAT}`, "
                                  "each with its own number"})

    problem = format_problem(brain.config.get("commit_format"))
    if problem:
        report(errors, f"{SCHEMA}/brain.md", "bad-commit-format", problem)

    for typedef in brain.types.values():
        for problem in _folder_problems(brain, typedef):
            report(errors, f"{SCHEMA}/types/{typedef.name}.md", "bad-area-folders", problem)

    for problem in policy.problems(brain):
        report(errors, f"{SCHEMA}/review.md", "bad-review-policy", problem)

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


def weekly_problem(cron):
    """Why a valid cron expression runs more than once a week, or None: one hour, and either one weekday or one day
    of the month."""
    _, hour, day, _, weekday = cron.split()
    if not hour.isdigit() or int(hour) > 23:
        return f"'{cron}' runs more than once a day: the review's hour field must be one number (0-23)"
    one_weekday = weekday.isdigit() and int(weekday) <= 7 and day == "*"
    one_day = day.isdigit() and 1 <= int(day) <= 31 and weekday == "*"
    if not (one_weekday or one_day):
        return (f"'{cron}' runs more than once a week: the review runs on one weekday (`0 4 * * 0`) or on one day "
                "of the month (`0 4 1 * *`)")
    return None


def _check_page(brain, p, error, warn):
    if not p.type:
        error("missing-type", "frontmatter has no 'type'")
        return
    typedef = brain.types.get(p.type)
    if typedef is None:
        error("unknown-type", f"type '{p.type}' is not defined in {SCHEMA}/types")
        return
    if not p.meta.get("title"):
        error("missing-title", "frontmatter has no 'title'")
    elif p.path.stem != p.title:
        error("title-mismatch", f"file name '{p.path.stem}' differs from title '{p.title}'")
    if p.title.lower() == INDEX[:-3].lower():
        error("reserved-title", f"'{p.title}' is reserved: {INDEX} is the folder's generated index")
    if BAD_TITLE.search(p.title):
        error("bad-title-chars", 'titles cannot contain \\ / : * ? " < > | # ^ [ ]')
    folder = Path(p.rel).parent.as_posix()
    home = typedef.folder_for(p.meta)
    if folder != home and not folder.startswith(home + "/"):
        area = p.meta.get("area")
        which = f"a '{p.type}' with area '{area}'" if typedef.area_folders and isinstance(area, str) \
            else f"type '{p.type}'"
        error("wrong-folder", f"{which} lives in {home}/")

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

    for ref in links.refs(brain, p.rel, p.body):
        if ref.page is None:
            error("broken-link", f"{ref.shown} in body matches no page", target=ref.name)
        elif ref.how == "alias":
            warn("alias-link", f"{ref.shown} in body is an alias of '{ref.page.title}'")
        if links.broken_anchor(brain, ref):
            warn("broken-anchor", f"{ref.shown} in body: '{ref.page.title}' has no heading '#{ref.anchor}'")
    for field, target in links.meta_links(p.meta, typedef):
        found, how = brain.lookup(target)
        if found is None:
            error("broken-link", f"'{target}' in field '{field}' matches no page", target=target)
            continue
        if how == "alias":
            warn("alias-link", f"'{target}' in field '{field}' is an alias of '{found.title}'")
        spec = typedef.fields.get(field) or {}
        expected = spec.get("to")
        if expected and found.type != expected:
            warn("link-type", f"field '{field}' expects a {expected}, '{found.title}' is a {found.type}")

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
    found = [r.page for r in links.refs(brain, page.rel, page.body)]
    found += [brain.lookup(t)[0] for field, t in links.meta_links(page.meta, brain.types.get(page.type))
              if field not in skip_fields]
    unique = {}
    for target in found:
        if target is not None:
            unique[target.rel] = target
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
    elif kind == "link" and not (isinstance(value, str) and value.strip()):
        error("bad-kind", f"'{name}' must be a page title")
    elif kind == "link" and "[[" in value:
        error("bad-kind", f"'{name}': write the page title ({value.strip('[] ')}), not a [[wikilink]]")
    elif kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        error("bad-kind", f"'{name}' must be a number")
    elif kind == "bool" and not isinstance(value, bool):
        error("bad-kind", f"'{name}' must be true or false")
    elif kind in ("string", "text") and isinstance(value, (list, dict)):
        error("bad-kind", f"'{name}' must be a single value")


def _folder_problems(brain, typedef):
    """Why a type's `area_folders` is unusable, one message each."""
    by_area = typedef.meta.get("area_folders")
    if by_area is None:
        return []
    if not isinstance(by_area, dict):
        return ["area_folders must map values of the `area` field to folders, e.g. "
                "{technical: technical/decisions}"]
    out = []
    spec = typedef.fields.get("area")
    values = (spec.get("values") or []) if isinstance(spec, dict) and spec.get("kind") == "enum" else None
    if values is None:
        out.append("area_folders needs an `area` enum field on the type: the page's area picks its folder")
    for area, folder in by_area.items():
        if values is not None and area not in values:
            out.append(f"area_folders: '{area}' is not a value of the `area` field {values}")
        if not isinstance(folder, str) or not folder.strip("/"):
            out.append(f"area_folders.{area} must be a folder")
            continue
        for other in brain.types.values():
            if other is not typedef and folder.strip("/") in other.folders:
                out.append(f"area_folders.{area}: {folder} is a folder of type '{other.name}'")
    return out


def _readme_pages(brain):
    """Brain-relative README.md files in type folders written as pages (with a `type`)."""
    out = []
    for folder in sorted(brain.type_folders()):
        base = brain.root / folder
        for path in sorted(p for p in base.rglob("*.md") if p.name == INDEX) if base.is_dir() else []:
            try:
                meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
            except (FrontmatterError, UnicodeDecodeError):
                meta = None
            if meta and meta.get("type"):
                out.append(path.relative_to(brain.root).as_posix())
    return out


def _other_texts(brain):
    """(rel, text) of non-page brain files that must be scanned: .pb/raw/, .pb/digests/, the review's queue,
    AGENTS.md."""
    root = brain.root
    candidates = [root / "AGENTS.md", root / pending.PATH]
    for folder in (RAW, DIGESTS):
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
        # brain/<path> typed from the repo root while --brain points at another brain (a routine worktree).
        return rel[len("brain/"):] if rel.startswith("brain/") else rel
