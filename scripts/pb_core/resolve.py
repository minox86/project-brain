"""Candidate pages for a name: exact title, alias, partial, fuzzy."""
import difflib
import re


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def resolve(brain, name, type_=None, limit=5):
    target = _norm(name)
    results = []
    for p in brain.pages():
        if type_ and p.type != type_:
            continue
        aliases = p.get("aliases")
        aliases = aliases if isinstance(aliases, list) else ([aliases] if aliases else [])
        names = [p.title] + [str(a) for a in aliases]
        normed = [_norm(n) for n in names]
        if normed[0] == target:
            match, score = "title", 1.0
        elif target in normed[1:]:
            match, score = "alias", 0.95
        elif target and any(target in n or (n and n in target) for n in normed):
            match, score = "partial", 0.75
        else:
            best = max(difflib.SequenceMatcher(None, target, n).ratio() for n in normed)
            if best < 0.6:
                continue
            match, score = "fuzzy", round(best * 0.7, 3)
        results.append({"title": p.title, "path": p.rel, "type": p.type, "match": match, "score": score})
    results.sort(key=lambda r: (-r["score"], r["title"]))
    return results[:limit]
