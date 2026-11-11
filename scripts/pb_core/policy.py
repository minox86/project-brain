"""Review policy (brain/.pb/schema/review.md): which brain changes go straight to the branch and which need a PR."""
LEVELS = ("low", "medium", "high")
AREAS = ("technical", "functional", "ux")
CHANGES = ("create", "update", "delete")
RULE_KEYS = {"type", "change", "fields", "area", "why"}

# Without review.md everything goes straight to the branch, as before the policy existed.
DEFAULT = {"direct_min_confidence": "low", "noise_to_review": False, "reviewers": {}, "watch": []}


def load(brain):
    meta = brain.review or {}
    policy = dict(DEFAULT)
    policy.update({k: v for k, v in meta.items() if k in DEFAULT and v is not None})
    policy["configured"] = bool(meta)
    return policy


def problems(brain):
    """Why review.md is unusable, one message each; empty when it is fine or absent."""
    meta = brain.review or {}
    if not meta:
        return []
    out = []
    level = meta.get("direct_min_confidence", "low")
    if level not in LEVELS:
        out.append(f"direct_min_confidence must be one of {list(LEVELS)}, got '{level}'")
    if not isinstance(meta.get("noise_to_review", False), bool):
        out.append("noise_to_review must be true or false")
    reviewers = meta.get("reviewers") or {}
    if not isinstance(reviewers, dict):
        out.append(f"reviewers must map areas {list(AREAS)} to lists of GitHub users or org/team")
        reviewers = {}
    for area, handles in reviewers.items():
        if area not in AREAS:
            out.append(f"reviewers: unknown area '{area}', use {list(AREAS)}")
        if handles is not None and not isinstance(handles, list):
            out.append(f"reviewers.{area} must be a list")
    watch = meta.get("watch") or []
    if not isinstance(watch, list):
        return out + ["watch must be a list of rules"]
    for i, rule in enumerate(watch, 1):
        if not isinstance(rule, dict) or "type" not in rule:
            out.append(f"watch rule {i} needs at least a 'type'")
            continue
        for key in set(rule) - RULE_KEYS:
            out.append(f"watch rule {i}: unknown key '{key}', use {sorted(RULE_KEYS)}")
        for name in as_list(rule["type"]):
            if name != "*" and name not in brain.types:
                out.append(f"watch rule {i}: type '{name}' is not defined in .pb/schema/types")
        for change in as_list(rule.get("change")):
            if change not in CHANGES:
                out.append(f"watch rule {i}: change must be one of {list(CHANGES)}, got '{change}'")
        for area in as_list(rule.get("area")):
            if area not in AREAS:
                out.append(f"watch rule {i}: area must be one of {list(AREAS)}, got '{area}'")
    return out


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
