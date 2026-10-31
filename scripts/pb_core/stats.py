"""Size of the brain: pages and words per type and area, budgets, largest pages."""


def stats(brain):
    by_type, by_area, over = {}, {}, []
    pages = [p for p in brain.pages() if p.type in brain.types]
    for p in pages:
        typedef = brain.types[p.type]
        for bucket, key in ((by_type, p.type), (by_area, typedef.area or "other")):
            entry = bucket.setdefault(key, {"pages": 0, "words": 0})
            entry["pages"] += 1
            entry["words"] += p.words
        if typedef.max_words and p.words > typedef.max_words:
            over.append({"title": p.title, "words": p.words, "max": typedef.max_words})
    largest = sorted(pages, key=lambda p: (-p.words, p.title))[:10]
    return {
        "pages": len(pages),
        "words": sum(p.words for p in pages),
        "by_type": by_type,
        "by_area": by_area,
        "over_budget": sorted(over, key=lambda o: (-o["words"], o["title"])),
        "largest": [{"title": p.title, "words": p.words} for p in largest],
    }
