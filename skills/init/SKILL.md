---
name: init
description: Creates the project brain (brain/ folder, living on the docs/brain branch) in the product monorepo through an interview that tailors the software-product schema to this project, sets up the GitHub workflows, bootstraps modules, interfaces and decisions from the code and ingests the documentation already in the repo into the chosen schema; also moves an existing brain from the default branch to docs/brain. Use when the user wants to initialise, create, set up or upgrade the project brain or pb, or when a pb command reports that there is no brain.
argument-hint: "[product name]"
---

# /pb:init — create the brain

Arguments: `$ARGUMENTS`

## How to ask

Ask every question of this skill with the **`AskUserQuestion` tool**, never as a text block:
- at most 4 questions per call, in dependency order; each question stands on its own (the user may see only the dialog), names what it is about and carries the facts from the repo that motivate it; `header` ≤ 12 characters;
- 2–4 options derived from the preset and the facts you gathered; the **recommended** one first, labelled "(Recommended)". Free answers go through the tool's built-in "Other";
- `multiSelect: true` where several answers go together (types to keep, modules to bootstrap, workflows to edit);
- `preview` for concrete artefacts to compare: a type's frontmatter with and without a field, `watch` rules before and after, a workflow edit.

Only if the tool is not available, ask in text: `❓ **Q1** - **<title>**: <question, options, facts>` then `➡️ <recommended answer>`, so "yes" accepts the recommendation.

## Where the brain lives

Not a question: say it once, in plain words. The brain lives on the branch `docs/brain`, created from the default branch. Everyone saves there directly through the `pb` skills; only pages on watched points wait in a review PR towards `docs/brain`. pb keeps one PR open from `docs/brain` to the default branch: the team merges it when it wants, with any merge method, and after each merge the `pb-brain-branch` workflow brings the default branch back into `docs/brain`. The default branch keeps its protection; `docs/brain` must stay open to pushes from everyone with write access.

## 0. Preconditions

1. Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`.
2. You must be in a git clone of the monorepo with `gh` logged in (`git rev-parse --show-toplevel`, `gh auth status`). If not, run `/pb:setup` first.
3. `PB workspace sync`:
   - it returns a `brain`: the brain exists. Stop: "The brain already exists on `docs/brain`. Use `/pb:schema` to change it."
   - `code: no-brain`, but the default branch has `brain/schema/VERSION` (`git cat-file -e origin/<default>:brain/schema/VERSION`): a brain from an earlier pb version, on the default branch. Offer the **upgrade** (section U) and skip the rest.
   - `code: no-brain` and no brain anywhere: create one, go on.
4. Never touch the user's checkout: everything is written in a temporary worktree (section 5).

## 1. Gather facts silently

Never ask the user what you can find yourself.

- `PB scan` → module candidates, API specs, ADRs, CODEOWNERS, READMEs, CI files, top-level folders, and the **documentation inventory** (`docs`: every Markdown, MDX, reStructuredText and AsciiDoc file outside ADR folders, hidden folders and test data, with `kind` `readme` / `docs` / `root` / `other`, `title` and `words`; `docs_words` is the total).
- Read the base preset: `BASE/../../presets/software-product/brain.md`, `BASE/../../presets/software-product/review.md` and every file in `BASE/../../presets/software-product/types/`.
- Read the root README and the READMEs of the main module candidates; skim a sample of ADRs and the first lines of each spec.
- **Documentation discovery.** Turn the inventory into groups by folder (e.g. `docs/architecture`, `docs/guides`, root files, module READMEs). Drop what is not product knowledge even if the scan kept it: tool or agent configuration (files with `name:`/`description:` frontmatter, prompt templates), generated API references, vendored or copied third-party docs. For each group, read the headings (`grep -n '^#' <files>`, or the first lines) and the last change (`git log -1 --format=%cs -- <path>`), and note which types its content would feed (features, concepts, modules, interfaces, environments, decisions, open questions). These facts also shape the schema: recurring subjects with no matching type are candidates for additional types, vocabulary in the docs feeds the glossary languages.
- Reviewer candidates: owners in CODEOWNERS (per path: backend, frontend, design system…); with `gh` available, the repo's teams (`gh api repos/<owner>/<repo>/teams`) and top committers per module path.
- Infer: product name (README title, package name), domain vocabulary (recurring nouns), module boundaries (workspaces, deployables), whether UX decisions are likely (frontend apps present), glossary languages.
- Only if the user names them: a Confluence space (Atlassian connector: pages tree) and Jira epics (JQL) to seed features and concepts. If the Atlassian connector is missing, guide the user to connect it (see **Connectors** in the conventions) or skip the seeding.

## 2. Build the design tree

The decisions that define the schema, each with the decisions that hang off it:

- Product name.
- For each preset type (`feature`, `epic`, `concept`, `module`, `interface`, `environment`, `decision`, `open-question`): keep / extend / drop. Keep `epic` when the team plans work in Jira epics; drop it otherwise. `decision` and `open-question` are system types: they can be extended, never dropped.
  - For kept types: extra fields, enum values (e.g. feature `status`, interface `kind`, environment `kind`), word budget (`max_words`), body sections.
- Additional types the project needs (only with a clear recurring need: e.g. `persona`, `integration-partner`, `metric`), each with area, folder, fields, budget, prose.
- Glossary languages (default `[en, it]`).
- Module map: which scan candidates are modules, their names, their `paths`, groupings.
- Thresholds in `brain.md` (archive, stale open questions, digest retention, context pack cap, raw cap).
- Review policy (`brain/schema/review.md`, the preset's template as the starting point): which changes are saved to `docs/brain` directly and which wait in a review PR.
  - Points of attention, once the types are settled: for each kept type, which changes need a human (any change, creation only, deletion, or only when given fields change, e.g. feature `status`, module `paths`). Recommend the preset's `watch` rules adapted to the kept and added types.
  - Confidence: below which level the writer's own rating holds a change (`direct_min_confidence`: `high` recommended; `medium` for a team that wants fewer PRs; `low` never holds by confidence).
  - Noise: whether pages still carrying a noise warning wait for review (`noise_to_review`, recommended `true`).
  - Reviewers per area: who reviews **technical** changes (modules, interfaces, environments, technical decisions), **functional** ones (features, concepts, functional decisions) and **design** ones (`ux` decisions); GitHub users or `org/team`. Recommend from the reviewer candidates. Cross-cutting pages (epics, open questions without area) ask every area.
- Sources to register now or later via `/pb:routine-setup` (Teams channels, Confluence spaces, Jira projects whose epics the brain follows).
- **GitHub** (section G).
- Bootstrap scope: which modules, specs and ADRs to turn into pages now.
- Existing documentation (section 6b): ingest all of it (recommended), only some groups, or none. Asked once the types are settled, since it is ingested into the chosen schema.

## 3. Grill in rounds

Interview the user relentlessly until the schema is fully settled. Work the tree in rounds:

- The **frontier** is every decision whose prerequisites are settled. Ask the whole frontier in one round (several `AskUserQuestion` calls if it has more than 4 questions); a question that depends on another open question waits for a later round.
- Ask as **How to ask** says: the recommended answer, derived from the preset and the facts you gathered, is the first option.
- After each answer, recompute the frontier. Facts are your job: if a question needs a fact from the repo or connectors, look it up instead of asking.
- Stop when the frontier is empty: every branch visited, nothing silently assumed.

## G. GitHub

Collect the facts first, never ask what `gh` can tell: the rules on `docs/brain` (`gh api repos/<repo>/rules/branches/docs/brain`, empty when nothing covers it), the Actions workflow permissions (`gh api repos/<repo>/actions/permissions/workflow`), and the product's CI (`PB scan` → `ci`). Then, in one round:

1. **`docs/brain` open to pushes.** If a ruleset or a protection pattern (e.g. `docs/*`, `*`) covers it, saves would fail: propose excluding `docs/brain` from it. Only a repo admin can change it: apply it with `gh api` if the user is one (`gh api repos/<repo> --jq .permissions.admin`), otherwise put it in the admin checklist of section 7.
2. **Workflows may push.** `pb-brain-branch` pushes to `docs/brain` with the workflow token (`contents: write`, declared in the workflow; an organisation or enterprise policy can still forbid it: check `gh api orgs/<org>/actions/permissions/workflow` when you can, and say what an org owner must allow). The workflow token cannot push changes to `.github/workflows/` that the default branch brings in: when product PRs often change workflows, recommend a `PB_BRAIN_TOKEN` repository secret (a fine-grained token or GitHub App with contents and workflows write on this repo), which `pb-brain-branch` uses when present.
3. **Product pipelines.** Saves are pushes to `docs/brain`, the brain PR is a PR with only `brain/`: pipelines that build, test or deploy on every push or PR would run for nothing. For each GitHub Actions workflow of the product that runs on `push` without a branch filter, or on `pull_request` without `paths-ignore`, offer (`multiSelect`, the edit as a `preview`) to add `branches-ignore: ["docs/brain"]` under `push` and `paths-ignore: ["brain/**"]` under `pull_request`; never add `paths-ignore` to a workflow whose jobs are **required** checks on the default branch (the brain PR would wait for a check that never runs): leave those as they are. Pipelines outside GitHub Actions: give the exact instructions, do not edit them.
4. **Required checks.** Recommend making `validate` and `brain-only` (from `pb-validate`) required on the default branch: they run on every PR and pass when no brain page changed, so code PRs are never blocked.

## 4. Confirm

Show the final schema in one block in the chat: types table (area, folder, fields, budget), thresholds, glossary languages, review policy (watched points, confidence threshold, reviewers per area), module map, bootstrap scope, documentation to ingest (groups, files, words), GitHub changes (applied now or for an admin) and workflow edits. Then one `AskUserQuestion`: confirm / change something / stop. Do not write anything before it.

## 5. Scaffold and apply the schema

1. Temporary worktree from the default branch, so the user's checkout is never touched: `git fetch -q origin`, then `git worktree add -q --detach <tmp> origin/<default>`. Run every following command and edit every file there.
2. `PB scaffold --repo <tmp> --product "<name>"` (creates `brain/`, the `pb-validate` and `pb-brain-branch` workflows, the CLAUDE.md pointer, the shared `.claude/settings.json` that enables the plugin for every clone, vendored toolkit). Report `skipped` workflows if any already existed, and check them against the templates.
3. Apply the interview results by editing `<tmp>/brain/schema/brain.md`, `review.md` and `types/*.md`. In `review.md` set `watch`, `direct_min_confidence`, `noise_to_review` and `reviewers`; check each handle with `gh api users/<login>` or `gh api orgs/<org>/teams/<slug>`, and keep the prose in sync with the rules. For the types: add/remove fields and enum values, set budgets, rewrite prose so it says when to create, when not to, body structure and budget. Delete dropped non-system type files; add new type files in the same format.
4. `PB --brain <tmp>/brain validate` must pass on the empty brain.

## 6. Bootstrap content

Propose, as one numbered list, the initial pages:
- one `module` per confirmed module, with `paths` and a 2–4 line `## Responsibility` drawn from its README/manifest;
- one `interface` per spec worth a page (`spec_path` set, `provided_by` the owning module);
- one `decision` (`area: technical`, `status: accepted`) per existing ADR, summarised and linked to the ADR file — never copied;
- optionally `feature` and `concept` pages from the Confluence space the user named, and `epic` pages for the active Jira epics that are discussed beyond their ticket.

Ask with `AskUserQuestion` (`multiSelect`, one option per group of pages: modules, interfaces, decisions, features and concepts, epics; "none" is the empty selection). Write them under `<tmp>/brain`, applying the significance gate and the writing rules; prefer fewer, accurate pages.

## 6b. Ingest the existing documentation

Skip when the discovery of section 1 found nothing worth ingesting; say so in one line.

1. **Ask.** One `AskUserQuestion`, with the facts in the question: "The repo has <N> documentation files (<W> words) in <G> groups: <group (files)>, … Ingest all of it into the brain now, following the schema we just agreed?". Options: **Ingest all (Recommended)** · **Choose the groups** · **Not now** (later with `/pb:put <folder>`). On "Choose the groups", a second `multiSelect` question, one option per group (more than 4 groups: by top folder, or several calls).
2. **Read and analyse**, group by group, one file at a time, with the schema of section 5 (the types in `<tmp>/brain/schema/types/`). Apply the **Analyse** rules of `/pb:put` (`BASE/../put/SKILL.md`, section 3) to each file:
   - extract features, concepts, modules, interfaces, environments, decisions and open questions; route each item to the type whose prose says it belongs there;
   - the significance gate holds: setup steps, how-tos for running the code, changelogs and plans of finished work are dropped; implementation plans keep only the decisions they record;
   - **merge, never duplicate**: resolve each entity with `PB --brain <tmp>/brain resolve` against the pages already written (section 6 and earlier files); a module README enriches the module page, an ADR already turned into a decision is not ingested twice;
   - the doc stays authoritative in the repo: summarise and link it, never copy it; cite it inline and in `sources` as `repo:<path>`; do not capture it in `raw/`, it is already versioned;
   - check claims that the code can contradict (module boundaries, endpoints, names) against the code; a contradiction, or two docs that disagree, becomes an `open-question` citing both, never a silent pick. A doc not changed for over a year while the code it describes changed since (`git log -1 --format=%cs -- <module paths>`) is a weak source: say so in the page and prefer an `open-question` for its doubtful claims.
   With many files (more than ~30, or over ~50,000 words), you may hand each group to a subagent with `writing.md`, the schema files and these rules: it returns proposed changes (page · create/update · content · sources), it writes nothing; you merge the proposals and resolve overlaps.
3. **Plan.** Show the list of pages to create or update, grouped by type, each with the docs it comes from, plus the files that gave nothing and why (one line per group). Confirm with one `AskUserQuestion`: write all / change something / skip.
4. **Write** under `<tmp>/brain`, following each type's prose and budget, then `PB --brain <tmp>/brain validate`: fix every error before going on.

## 7. Close

1. Commit in the temporary worktree: `PB --brain <tmp>/brain commit -m "pb(init): create brain for <product>" --allow-default --include CLAUDE.md .claude/settings.json .github/workflows/pb-validate.yml .github/workflows/pb-brain-branch.yml` (leave out workflows reported as `skipped`). Then the generated files: `PB --brain <tmp>/brain generate`, `git -C <tmp> add brain`, `git -C <tmp> commit -qm "pb(generate): refresh generated files"` (init is the only place that runs `PB generate` by hand: there is no save yet).
2. Create `docs/brain` with it: `git -C <tmp> push -q origin HEAD:refs/heads/docs/brain`.
3. Open the brain PR: `gh pr create --head docs/brain --base <default> --title "Brain updates" --body <what this first PR brings: the brain, the pb workflows, the CLAUDE.md pointer and the plugin settings; merging it turns on the workflows on the default branch; afterwards the PR is reopened by pb with each new save>`. The product pipeline edits of section G are code: put them in a separate branch and PR towards the default branch, never on `docs/brain`.
4. `git worktree remove --force <tmp>`, then `PB workspace sync` in the user's clone: it must return the brain.

Then explain the next steps, in a few lines:
- what the documentation ingestion brought in (pages per type, files skipped), and how to ingest more later (`/pb:put <path>`);
- everyone reads and writes the brain from Claude Code with the `pb` skills; git stays invisible, every save is visible to everyone at once on `docs/brain`; pages on points watched in `brain/schema/review.md` wait for the area reviewers in a PR;
- merge the brain PR now, to turn on the workflows; later, merge it whenever the code branches should carry the brain (any merge method);
- newcomers run `/pb:setup` (tools, GitHub login, clone);
- GitHub settings left to an admin, if any, as a checklist;
- `/pb:routine-setup` to feed the brain nightly from Teams, Confluence and merged PRs;
- Cowork users read the brain through the GitHub connector, on the branch `docs/brain`.

## U. Upgrade an existing brain

A brain from an earlier pb version lives on the default branch. Explain the move in plain words (where the brain will live, what changes for the team: saves no longer go through their code PRs) and ask to confirm. Then:

1. Run section G (GitHub).
2. Temporary worktree from the default branch (as in section 5), `PB scaffold --repo <tmp> --upgrade` (rewrites `pb-validate`, adds `pb-brain-branch`, deletes `pb-generate` (every save regenerates now), enables the plugin, refreshes the toolkit and the writing rule in `brain/AGENTS.md`), commit with `PB --brain <tmp>/brain commit -m "pb(init): move the brain to docs/brain" --allow-default --include .claude/settings.json .github/workflows/pb-validate.yml .github/workflows/pb-brain-branch.yml`, adding `.github/workflows/pb-generate.yml` only when the upgrade reported deleting it; then steps 2–4 of section 7.
3. If `routine.branch` in `brain/schema/sources.md` is not `docs/brain`, run `/pb:routine-setup`: it sets it and updates the routine's prompt. Until that review PR is merged, the routine keeps writing where it did.
4. Tell developers: pages written in code branches before the move reach the default branch with their PRs, and `docs/brain` at the next merge of the brain PR (on a conflicting edit, the `docs/brain` version wins); from now on, use the `pb` skills.
