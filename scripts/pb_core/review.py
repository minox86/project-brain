"""Flags the brain changes that are watched, and their area reviewers, by the policy in schema/review.md."""
from pathlib import Path

from . import policy
from .changes import changed_pages
from .errors import UsageError
from .validate import brain_rel, noise, page_targets


def review(brain, base="HEAD", confidence=(), noise_holds=True):
    """Which changed pages are watched (flagged for their area reviewers), why, and who reviews them. `confidence`
    holds "PATH=LEVEL" items. `noise_holds=False` (interactive saves, where the user confirmed the pages): noise
    warnings never flag a page. The keys `route`/`direct`/`review` are kept: `review` lists the flagged pages."""
    rules = policy.load(brain)
    changed = changed_pages(brain, base)
    if changed is None:
        raise UsageError(f"cannot compare the brain with '{base}': run inside its git repo, with that commit present")
    levels, ignored = _levels(brain, confidence, changed)
    pages = {p.rel: p for p in brain.pages() if p.type in brain.types}
    flagged = {}

    def flag(rel, reason):
        flagged.setdefault(rel, []).append(reason)

    for rel, info in sorted(changed.items()):
        page = pages.get(rel)
        meta, old = (page.meta if page else {}), (info["old"] or {})
        type_ = (page.type if page else None) or old.get("type")
        area = page_area(brain, type_, meta or old)
        for rule in rules["watch"]:
            if _matches(rule, type_, info["change"], meta, old, area):
                flag(rel, "watch: " + (rule.get("why") or _describe(rule)))
        level = levels.get(rel, "high")
        if policy.LEVELS.index(level) < policy.LEVELS.index(rules["direct_min_confidence"]):
            flag(rel, f"confidence: {level}")
    if rules["noise_to_review"] and noise_holds:
        for p, code, _ in noise(brain, changed):
            flag(p.rel, f"noise: {code}")

    # A page that links a new flagged page is flagged too: its reviewers see both.
    created = {rel for rel, info in changed.items() if info["change"] == "create"}
    moved = True
    while moved:
        moved = False
        for rel in sorted(changed):
            if rel in flagged or rel not in pages:
                continue
            for target in page_targets(brain, pages[rel]):
                if target.rel in flagged and target.rel in created:
                    flag(rel, f"links [[{target.title}]], new and under review")
                    moved = True
                    break

    items = []
    for rel in sorted(flagged):
        page = pages.get(rel)
        old = changed[rel]["old"] or {}
        type_ = (page.type if page else None) or old.get("type")
        items.append({"path": rel, "title": page.title if page else Path(rel).stem, "type": type_,
                      "change": changed[rel]["change"], "area": page_area(brain, type_, page.meta if page else old),
                      "reasons": flagged[rel]})
    return {
        "route": "pr" if items else "direct",
        "policy": "schema/review.md" if rules["configured"] else "default (no schema/review.md: everything direct)",
        "direct": sorted(rel for rel in changed if rel not in flagged),
        "review": items,
        "reviewers": reviewers_for(rules, items),
        "ignored_confidence": ignored,
        "markdown": _markdown(items),
    }


def page_area(brain, type_, meta):
    """technical, functional or ux; None for cross-cutting pages with no area of their own."""
    if meta.get("area") in policy.AREAS:
        return meta["area"]
    typedef = brain.types.get(type_)
    return typedef.area if typedef and typedef.area in policy.AREAS else None


def reviewers_for(rules, items):
    """GitHub users and team slugs for the areas of the flagged pages; a page with no area asks every area."""
    configured = rules["reviewers"] or {}
    areas = []
    for item in items:
        for area in [item["area"]] if item["area"] else policy.AREAS:
            if area not in areas:
                areas.append(area)
    handles, users, teams = [], [], []
    for area in areas:
        for handle in configured.get(area) or []:
            handle = str(handle).lstrip("@")
            if handle in handles:
                continue
            handles.append(handle)
            if "/" in handle:
                teams.append(handle.split("/", 1)[1])
            else:
                users.append(handle)
    return {"areas": areas, "handles": handles, "users": users, "teams": teams}


def _matches(rule, type_, change, meta, old, area):
    types = policy.as_list(rule.get("type"))
    if "*" not in types and type_ not in types:
        return False
    changes = policy.as_list(rule.get("change"))
    if changes and change not in changes:
        return False
    areas = policy.as_list(rule.get("area"))
    if areas and area not in areas:
        return False
    fields = policy.as_list(rule.get("fields"))
    return not fields or any(meta.get(f) != old.get(f) for f in fields)


def _describe(rule):
    parts = [", ".join(policy.as_list(rule["type"]))]
    if rule.get("change"):
        parts.append(" or ".join(policy.as_list(rule["change"])))
    if rule.get("area"):
        parts.append("area " + ", ".join(policy.as_list(rule["area"])))
    if rule.get("fields"):
        parts.append("fields " + ", ".join(policy.as_list(rule["fields"])))
    return " · ".join(parts)


def _levels(brain, items, changed):
    levels, ignored = {}, []
    for item in items or ():
        path, sep, level = str(item).rpartition("=")
        if not sep or level not in policy.LEVELS:
            raise UsageError(f"--confidence takes PATH=LEVEL with LEVEL in {list(policy.LEVELS)}, got '{item}'")
        rel = brain_rel(brain, path)
        if rel.startswith("brain/") and rel not in changed:
            rel = rel[len("brain/"):]
        if rel in changed:
            levels[rel] = level
        else:
            ignored.append(path)
    return levels, ignored


def _markdown(items):
    if not items:
        return ""
    lines = ["Brain changes that need a human look before they count (policy: `brain/schema/review.md`).", "",
             "| Page | Change | Area | Why |", "|---|---|---|---|"]
    for item in items:
        lines.append(f"| `{item['path']}` | {item['change']} | {item['area'] or 'cross'} | "
                     f"{'; '.join(item['reasons'])} |")
    return "\n".join(lines) + "\n"
