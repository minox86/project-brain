"""The review's queue: maintenance doubts waiting for a person, in brain/.pb/pending.md.

One line per doubt. An open line waits for an answer; a ticked line is a "no" the owner gave ("leave it as it is"),
kept so that no later review queues or applies that item again. A number is never given twice: the file
remembers the last one given (`<!-- last: R<n> -->`), so a report that names R3 names one item for ever. Knowledge doubts are not here: they are
open-question pages. `waiting` counts both, by the area of competence that can settle them.
"""
import re

from . import policy
from .brain import DIGESTS
from .errors import UsageError

PATH = ".pb/pending.md"
AREAS = ("functional", "technical", "any")
TAGS = ("DUPLICATE", "CONTRADICTION", "MOVED", "OUTDATED", "SUPERSEDED", "GLOSSARY", "QUALITY", "LINK", "SCHEMA",
        "JIRA")
FORMAT = "- [ ] R<n> · <functional|technical|any> · <TAG> · <pages> · <doubt> · suggested: <action> · found: <date>"
HEADER = ("# Pending review items\n\nMaintenance doubts the review could not settle alone. Written by `/pb:review` "
          "through `PB pending`; answered with `/pb:review`.\nA ticked line is a \"no\" that stays: the review never "
          "proposes it again.\n\n<!-- last: R0 -->\n\n")
LINE = re.compile(r"- \[(?P<done>[ xX])\] R(?P<n>\d+) · (?P<area>%s) · (?P<tag>%s) · (?P<text>\S.*)$"
                  % ("|".join(AREAS), "|".join(TAGS)))
REPORT = re.compile(r"\d{4}-\d{2}-\d{2}-review\.md$")
NUMBER = re.compile(r"- \[.\] R(\d+)\b")
LAST = re.compile(r"<!-- last: R(\d+) -->")
MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
KEPT = " · kept: "


def _parse(text):
    """(items, bad) of a queue text: a second line with a number already seen and a leftover conflict marker are bad."""
    items, bad, seen = [], [], set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith(MARKERS):
            bad.append({"line": number, "text": line, "why": "a merge conflict marker"})
            continue
        if not line.startswith("- ["):
            continue
        match = LINE.match(line)
        if not match:
            bad.append({"line": number, "text": line, "why": "not a queue line"})
            continue
        n = int(match.group("n"))
        if n in seen:
            bad.append({"line": number, "text": line, "why": f"R{n} is used twice"})
            continue
        seen.add(n)
        items.append({"n": n, "done": match.group("done") != " ", "area": match.group("area"),
                      "tag": match.group("tag"), "text": match.group("text"), "line": number})
    return items, bad


def _last(text):
    """The last number given: the remembered one, or the highest in the file (malformed lines included, so that a
    repaired line never meets a twin)."""
    return max([int(n) for n in LAST.findall(text) + NUMBER.findall(text)], default=0)


def _remember(text, number):
    """`text` with the last number given set to `number`, the note written before the first line when absent."""
    note = f"<!-- last: R{number} -->"
    if LAST.search(text):
        return LAST.sub(note, text, count=1)
    lines = text.split("\n")
    at = next((i for i, raw in enumerate(lines) if raw.strip().startswith(("- [",) + MARKERS)), None)
    if at is None:
        return text + ("" if not text or text.endswith("\n") else "\n") + note + "\n\n"
    return "\n".join(lines[:at] + [note, ""] + lines[at:])


def read(brain):
    """Queue lines, and the lines that look like one (`- [`) but do not follow the format."""
    path = brain.root / PATH
    if not path.is_file():
        return {"items": [], "bad": []}
    items, bad = _parse(path.read_text(encoding="utf-8"))
    return {"items": items, "bad": bad}


def area_of(brain, page):
    """functional, technical or any: the competence that can settle a doubt about this page (ux is functional)."""
    area = page.get("area")
    if area not in policy.AREAS:
        typedef = brain.types.get(page.type)
        area = typedef.area if typedef else None
    if area == "ux":
        return "functional"
    return area if area in AREAS else "any"


def waiting(brain):
    """Open queue lines and open questions by area, and the latest review report."""
    out = {area: 0 for area in AREAS}
    for item in read(brain)["items"]:
        if not item["done"]:
            out[item["area"]] += 1
    for page in brain.pages():
        if page.type == "open-question" and page.get("status", "open") in (None, "open"):
            out[area_of(brain, page)] += 1
    out["total"] = sum(out[area] for area in AREAS)
    digests = brain.root / DIGESTS
    reports = sorted(p.name for p in digests.glob("*-review.md") if REPORT.match(p.name)) if digests.is_dir() else []
    out["report"] = f"brain/{DIGESTS}/{reports[-1]}" if reports else None
    return out


def pr_line(counts):
    """One line for the description of the Brain updates PR; empty with nothing waiting and no report."""
    if not counts["total"] and not counts["report"]:
        return ""
    line = ("Waiting for a decision (run `/pb:review`): " + ", ".join(f"{area} {counts[area]}" for area in AREAS)
            + ".") if counts["total"] else "Nothing is waiting for a decision."
    if counts["report"]:
        line += f" Latest review report: `{counts['report']}`."
    return line


def add(brain, entry, today):
    """Append an open line `AREA · TAG · pages · doubt · suggested: …` with the next number. Returns the item."""
    entry = " ".join(str(entry).split())
    parts = entry.split(" · ", 2)
    if len(parts) < 3 or parts[0] not in AREAS or parts[1] not in TAGS or not parts[2].strip():
        raise UsageError(f"a queue entry is `<{'|'.join(AREAS)}> · <{'|'.join(TAGS)}> · <pages> · <doubt> · "
                         "suggested: <action>`")
    path = brain.root / PATH
    text = path.read_text(encoding="utf-8") if path.is_file() else HEADER
    number = _last(text) + 1
    text = _remember(text, number)
    if text and not text.endswith("\n"):
        text += "\n"
    line = f"- [ ] R{number} · {entry} · found: {today.isoformat()}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + line + "\n", encoding="utf-8")
    return {"n": number, "done": False, "area": parts[0], "tag": parts[1], "text": line.split(" · ", 3)[3]}


def settle(brain, number, kept=None):
    """Remove line R<number> (answered), or with `kept` tick it and record the reason (a "no" that stays)."""
    path = brain.root / PATH
    item = next((i for i in read(brain)["items"] if i["n"] == number), None)
    if item is None:
        raise UsageError(f"no R{number} in brain/{PATH}")
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    index = item["line"] - 1
    if kept is None:
        del lines[index]
    else:
        reason = " ".join(str(kept).split())
        if not reason:
            raise UsageError("--kept needs the reason")
        if item["done"]:
            raise UsageError(f"R{number} is already ticked")
        lines[index] = lines[index].replace("- [ ]", "- [x]", 1) + f" · kept: {reason}"
    # Remembered before the line goes: the number of a removed item is never given again.
    path.write_text(_remember("\n".join(lines), _last(text)), encoding="utf-8")
    return {"n": number, "kept": kept is not None}


def _identity(item):
    """What a line is about, whatever its number and whether it is ticked."""
    return item["area"], item["tag"], item["text"].split(KEPT)[0]


def merge_texts(base, ours, theirs):
    """One queue out of two that diverged from `base` (texts; None: no file). An item either side removed stays
    removed, a tick wins over an open line, an item either side added is kept, and a number two different items
    share goes to the first while the other gets the next free one, past every number either side ever gave.
    `ours` gives the order and the header."""
    sides = [_parse(text or "")[0] for text in (base, ours, theirs)]
    known = [{_identity(item): item for item in side} for side in sides]
    old, mine, other = known
    lines, used = [], set()
    free = max(_last(text or "") for text in (base, ours, theirs))
    for key in list(mine) + [key for key in other if key not in mine]:
        if key in old and (key not in mine or key not in other):
            continue  # answered on one side
        versions = [side[key] for side in (mine, other) if key in side]
        item = next((v for v in versions if v["done"]), versions[0])
        number = item["n"]
        if number in used:
            free += 1
            number = free
        used.add(number)
        lines.append(f"- [{'x' if item['done'] else ' '}] R{number} · {item['area']} · {item['tag']} · {item['text']}")
    head = []
    for raw in (ours if ours is not None else theirs or HEADER).splitlines():
        if raw.strip().startswith("- [") or raw.strip().startswith(MARKERS):
            break
        head.append(raw)
    while head and not head[-1].strip():
        head.pop()
    return _remember("\n".join(head + ([""] if head else []) + lines) + "\n", free)
