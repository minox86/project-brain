---
name: lint
description: Maintains the project brain — finds schema errors, pages over their word budget, duplicate candidates, orphans, stale open questions, archivable items, modules whose paths no longer exist and links to superseded decisions — and with --fix proposes merges, condensations and cleanups. Use when the user asks to check, clean up, tidy, shrink or maintain the brain.
argument-hint: "[--fix]"
---

# /pb:lint — maintenance

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

1. `PB lint`. Report findings grouped by code, with counts, then the size summary from `stats` (pages, words, over budget, largest).
2. Without `--fix`, stop here and suggest the most valuable fixes first: schema errors, over-budget pages, duplicates.
3. With `--fix`, propose per group, as a numbered list with previews:
   - **schema errors / broken links** — the corrected field or link;
   - **over-budget** — a condensed version of the page (keep facts, drop repetition and detail that fails the significance gate, move detail to links);
   - **duplicate-candidate** — merge into one page: keep the better title, move the other title to `aliases`, rewrite every `[[link]]` to the kept title across the brain, delete the other file;
   - **orphan** — link it from the right page, or delete it if it fails the significance gate;
   - **stale-open-question** — ask whether it is resolved (→ decision), dropped, or still open (refresh `updated`);
   - **archivable** — delete it (history stays in git) or keep it; for an epic, first check that what is still true lives on feature, concept, module or decision pages;
   - **dead-module-paths** — update `paths` from the current repo layout, or delete the module;
   - **superseded-referenced** — relink to the successor decision.
4. Apply what the user confirms. Deletions and merges are destructive: list them explicitly before applying.
5. Closing flow: `PB save -m "pb(lint): <summary>"`.
