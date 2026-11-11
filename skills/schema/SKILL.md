---
name: schema
description: Shows and evolves the project brain schema (types, fields, budgets, thresholds) and applies proposals with the needed page migrations. Use when the user asks what types the brain has, wants to add or change a type or field, or asks to review or apply schema proposals.
argument-hint: "[show | propose | apply <Pn> | <change in plain words>]"
---

# /pb:schema — evolve the schema

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

## show (default)

Table of types from `brain/schema/types/*.md`: name, area, folder, fields (with enum values), required, budget, system. Then the thresholds in `brain/schema/brain.md`, the review policy in `brain/schema/review.md` (watched points, confidence threshold, noise, reviewers per area; "not configured: no change is flagged for review" when the file is missing) and open proposals in `brain/schema/proposals.md`.

## propose

1. Collect signals: open lines in `proposals.md`; `PB validate` warnings (`unknown-field` recurring on a type, `link-type`); `PB stats` (types with many pages over budget, empty types); `PB lint` (`duplicate-candidate` clusters suggesting a missing type).
2. Propose numbered changes, each with the reason, the pages affected and the migration needed. Append accepted-for-later ones to `proposals.md`.
3. A domain need the schema lacks (rules restated in several features, norms, cross-feature processes, editions, KPIs): propose the matching type from `BASE/../../presets/domain-types/` (its README lists the signals), adapted to the product.

## Review policy

Changes like "send feature status changes to review", "design reviews go to @acme/design", "only low confidence needs a reviewer" edit `brain/schema/review.md`: `watch` rules, `direct_min_confidence`, `noise_to_review`, `reviewers`. The file's prose lists the fields. Missing file (brain created before the policy existed): copy `BASE/../../presets/software-product/review.md` and adapt it with the user. Show the rule before and after, confirm, then `PB validate` (it reports `bad-review-policy`) and save like any schema change. When a type is renamed or dropped, update the rules that name it.

## apply <Pn> or a change in plain words

1. Describe the exact change: type files edited, fields renamed/added/removed, folders moved, pages to migrate (list them).
2. Refuse to remove `decision` or `open-question` or their base fields (`area`, `status`, `affects`, `supersedes`, `resolved_by`, `resolves`): the toolkit relies on them.
3. Wait for explicit confirmation.
4. Edit the type files (and the `watch` rules in `review.md` that name a renamed or removed type or field); migrate pages (rename fields, move files, fix every `[[link]]` when a title changes — search the whole brain).
5. Mark the proposal `- [x]` in `proposals.md`.
6. `PB validate` must pass with no new errors.
7. Save on its own, following the closing flow: `PB save <files written>`. Changes under `schema/` are always watched: the PR that carries them asks the reviewers.
