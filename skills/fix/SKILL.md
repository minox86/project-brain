---
name: fix
description: Corrects wrong information in the project brain — finds every page asserting it, classifies the error (misrecorded, outdated, contested), corrects or supersedes, traces the source so sync does not re-ingest it, and logs the correction. Use when someone says the brain is wrong, outdated or inaccurate about something ("the brain says X but actually Y", "this decision is wrong", "fix the page about…").
argument-hint: "<what is wrong> [→ what is right] [evidence]"
---

# /pb:fix — correct the brain

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

## 1. Understand the correction

You need: what is wrong, what is right, and the evidence (a file in the repo, a Jira issue, a Confluence page, "verified in code", a decision taken). Ask only for what is missing. If the evidence is in the repo, read it and confirm it actually supports the correction.

## 2. Locate

Find every page asserting the wrong fact:
- the page the user named (`PB resolve`);
- a search across `brain/` for the claim, its key terms, the concept's aliases (`grep -ril`);
- pages linked from those (`PB context --feature`/`--paths` when relevant).

Ignore generated files (the `README.md` files, `.pb/context/`): every save rebuilds them.

## 3. Classify

- **Misrecorded** — the brain never matched reality: correct in place.
- **Outdated** — it was true and changed:
  - a `decision` is never rewritten: create a new decision with `supersedes: <old title>`, set the old one to `status: superseded`, update `affects` pages to link the new one;
  - knowledge pages (feature, process, concept, module, contract, environment): update the content.
- **Contested** — the evidence conflicts with an external source of truth (Confluence PRD, Jira acceptance criteria): do not pick a side; create an `open-question` citing both and link it from the affected pages.

## 4. Trace the origin

Read the `sources` of the wrong claim. If it came from an ingested source (Teams thread, Confluence page, PR), record it so sync will not bring it back: `PB state suppress <teams|confluence|github|jira> "<the wrong claim, one sentence>"`. It travels with this branch's PR; never touch the cursors in the same file.

## 5. Preview and correct

Show, for every page, the exact lines before and after. After confirmation:
- replace the wrong statement (no "previously it said…" prose in the body);
- add the evidence to `sources` as `fix:YYYY-MM-DD` plus the evidence reference, and cite it inline;
- set `updated`.

## 6. Log and close

`PB correction --page <rel path> --wrong "<wrong>" --right "<right>" --evidence "<evidence>"` once per corrected page. Then the closing flow: `PB save <files written>`.
