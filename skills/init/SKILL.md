---
name: init
description: Creates the project brain (brain/ folder) in the product monorepo through a grill-style interview that tailors the software-product schema to this project, then bootstraps modules, interfaces and decisions from the code. Use when the user wants to initialise, create or set up the project brain or pb, or when any pb command runs in a repo without brain/.
argument-hint: "[product name]"
---

# /pb:init — create the brain

Arguments: `$ARGUMENTS`

## 0. Preconditions

1. Read `BASE/../../references/conventions.md`.
2. `PB version`. If `brain` is not null, stop: "A brain already exists at <path>. Use `/pb:schema` to change it."
3. You must be in a git repo (the monorepo): `git rev-parse --show-toplevel`. If not, stop and say so.
4. If the current branch is the default branch, propose creating `pb/init` (`git switch -c pb/init`) before writing anything.

## 1. Gather facts silently

Never ask the user what you can find yourself.

- `PB scan` → module candidates, API specs, ADRs, CODEOWNERS, READMEs, CI files, top-level folders.
- Read the base preset: `BASE/../../presets/software-product/brain.md` and every file in `BASE/../../presets/software-product/types/`.
- Read the root README and the READMEs of the main module candidates; skim a sample of ADRs and the first lines of each spec.
- Infer: product name (README title, package name), domain vocabulary (recurring nouns), module boundaries (workspaces, deployables), whether UX decisions are likely (frontend apps present), glossary languages.
- Only if the user names them: a Confluence space (Atlassian connector: pages tree) and Jira epics (JQL) to seed features and concepts.

## 2. Build the design tree

The decisions that define the schema, each with the decisions that hang off it:

- Product name.
- For each preset type (`feature`, `epic`, `concept`, `module`, `interface`, `environment`, `decision`, `open-question`): keep / extend / drop. Keep `epic` when the team plans work in Jira epics; drop it otherwise. `decision` and `open-question` are system types: they can be extended, never dropped.
  - For kept types: extra fields, enum values (e.g. feature `status`, interface `kind`, environment `kind`), word budget (`max_words`), body sections.
- Additional types the project needs (only with a clear recurring need: e.g. `persona`, `integration-partner`, `metric`), each with area, folder, fields, budget, prose.
- Glossary languages (default `[en, it]`).
- Module map: which scan candidates are modules, their names, their `paths`, groupings.
- Thresholds in `brain.md` (archive, stale open questions, digest retention, context pack cap, raw cap).
- Sources to register now or later via `/pb:routine-setup` (Teams channels, Confluence spaces, Jira projects whose epics the brain follows).
- Bootstrap scope: which modules, specs and ADRs to turn into pages now.

## 3. Grill in rounds

Interview the user relentlessly until the schema is fully settled. Work the tree in rounds:

- The **frontier** is every decision whose prerequisites are settled. Ask the whole frontier in one round; a question that depends on another open question waits for a later round.
- Number each question and give your recommended answer, derived from the preset and the facts you gathered. Word it so "yes" accepts the recommendation.
- Format:

      ❓ **Q1** - **<title>**: <question, options, the facts that motivate it>

      ➡️ <recommended answer>

      ---

- After each answer, recompute the frontier. Facts are your job: if a question needs a fact from the repo or connectors, look it up instead of asking.
- Stop when the frontier is empty: every branch visited, nothing silently assumed.

## 4. Confirm

Show the final schema in one block: types table (area, folder, fields, budget), thresholds, glossary languages, module map, bootstrap scope. Ask for explicit confirmation. Do not write anything before it.

## 5. Scaffold and apply the schema

1. `PB scaffold --product "<name>"` (creates `brain/`, CI workflows, the CLAUDE.md pointer, `.gitignore` entry, vendored toolkit). Report `skipped` workflows if any already existed, and confirm `default_branch` with the user: it is the branch `pb-generate.yml` runs on (fix the workflow if it is wrong).
2. Apply the interview results by editing `brain/schema/brain.md` and `brain/schema/types/*.md`: add/remove fields and enum values, set budgets, rewrite prose so it says when to create, when not to, body structure and budget. Delete dropped non-system type files; add new type files in the same format.
3. `PB validate` must pass on the empty brain.

## 6. Bootstrap content

Propose, as one numbered list, the initial pages:
- one `module` per confirmed module, with `paths` and a 2–4 line `## Responsibility` drawn from its README/manifest;
- one `interface` per spec worth a page (`spec_path` set, `provided_by` the owning module);
- one `decision` (`area: technical`, `status: accepted`) per existing ADR, summarised and linked to the ADR file — never copied;
- optionally `feature` and `concept` pages from the Confluence space the user named, and `epic` pages for the active Jira epics that are discussed beyond their ticket.

Ask: "Create all / choose by number / none". Apply the significance gate and the writing rules; prefer fewer, accurate pages.

## 7. Close

Closing flow of the conventions, committing the files scaffold created outside `brain/` too: `PB commit -m "pb(init): create brain for <product>" --include CLAUDE.md .gitignore .github/workflows/pb-validate.yml .github/workflows/pb-generate.yml` (leave out workflows reported as `skipped`). Then explain the next steps:
- the brain travels with this branch's PR; once merged, CI keeps `index.md`, `glossary.md` and `context/` up to date;
- enable auto-merge in the repo settings so brain-only PRs merge once `pb-validate` passes; `pb-generate` also runs hourly, because merges made by auto-merge do not trigger push workflows;
- `/pb:routine-setup` to feed the brain nightly from Teams, Confluence and merged PRs;
- non-developers read the brain from Cowork through the GitHub connector.
