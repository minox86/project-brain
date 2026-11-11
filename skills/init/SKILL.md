---
name: init
description: Creates the project brain (brain/ folder, arriving in the repo through an ordinary pull request) in the product monorepo through an interview that tailors the software-product schema to this project, sets up the GitHub workflow, bootstraps modules, contracts and decisions from the code and ingests the documentation already in the repo into the chosen schema; also brings the workflow and toolkit of an existing brain up to date. Pages are then written in the working branch and reach the default branch with the code PR; the nightly routine writes on `docs/brain` and its changes are brought to the default branch with `/pb:merge`. Use when the user wants to initialise, create, set up or upgrade the project brain or pb, or when a pb command reports that there is no brain.
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

Not a question: say it once, in plain words. The brain is the `brain/` folder of the repo. Developers write pages in their working branch, with the `pb` skills, and commit them with the code: they reach the default branch with the code PR, so the brain changes under the same review as the code. The nightly routine is the only writer on the branch `docs/brain` and keeps one PR from it to the default branch; nothing merges by itself, and the maintainer brings the routine's changes to the default branch with `/pb:merge`. Cowork users read the brain on the default branch. This init opens an ordinary PR from the branch `pb/init`; the default branch keeps its protection.

## 0. Preconditions

1. Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`.
2. You must be in a git clone of the monorepo with `gh` logged in (`git rev-parse --show-toplevel`, `gh auth status`). If not, run `/pb:setup` first.
3. Look for a brain: `git fetch -q origin`, then `git cat-file -e origin/<default>:brain/.pb/schema/VERSION`:
   - it exists and its vendored toolkit (`brain/.pb/toolkit/VERSION` on the default branch) has the plugin's version (`PB version`): the brain exists. Stop: "The brain already exists. Use `/pb:schema` to change it."
   - it exists with an older vendored toolkit: offer the **upgrade** (section U) and skip the rest.
   - it is missing but `brain/` is there (`git cat-file -e origin/<default>:brain/AGENTS.md` succeeds): the brain has the format of an earlier pb version. Stop: "This brain has the format of an earlier pb version: remove `brain/` and create it again with `/pb:init`." There is no migration.
   - no brain on the default branch: create one, go on (an open PR from `pb/init` means a previous init is waiting to be merged: say so and stop).
4. Never touch the user's checkout: everything is written in a temporary worktree (section 5).

## 1. Gather facts silently

Never ask the user what you can find yourself.

- `PB scan` → module candidates, API specs, ADRs, CODEOWNERS, READMEs, CI files, top-level folders, and the **documentation inventory** (`docs`: every Markdown, MDX, reStructuredText and AsciiDoc file outside ADR folders, hidden folders and test data, with `kind` `readme` / `docs` / `root` / `other`, `title` and `words`; `docs_words` is the total).
- Read the base preset: `BASE/../../presets/software-product/brain.md`, `BASE/../../presets/software-product/review.md` and every file in `BASE/../../presets/software-product/types/`; then the catalogue of domain types, `BASE/../../presets/domain-types/README.md`.
- Read the root README and the READMEs of the main module candidates; skim a sample of ADRs and the first lines of each spec.
- **Documentation discovery.** Turn the inventory into groups by folder (e.g. `docs/architecture`, `docs/guides`, root files, module READMEs). Drop what is not product knowledge even if the scan kept it: tool or agent configuration (files with `name:`/`description:` frontmatter, prompt templates), generated API references, vendored or copied third-party docs. For each group, read the headings (`grep -n '^#' <files>`, or the first lines) and the last change (`git log -1 --format=%cs -- <path>`), and note which types its content would feed (features, processes, concepts, modules, contracts, environments, decisions, open questions). These facts also shape the schema: recurring subjects with no matching type are candidates for additional types, vocabulary in the docs feeds the glossary languages.
- Reviewer candidates: owners in CODEOWNERS (per path: backend, frontend, design system…); with `gh` available, the repo's teams (`gh api repos/<owner>/<repo>/teams`) and top committers per module path.
- Infer: product name (README title, package name), domain vocabulary (recurring nouns), module boundaries (workspaces, deployables), whether UX decisions are likely (frontend apps present), glossary languages.
- External systems (future `integration` pages): SDK and client dependencies in the manifests (payment, identity, e-invoicing, messaging), base URLs and env var names such as `*_API_URL` in config samples (names only, never values), integration folders (`integrations/`, `clients/`, `adapters/`).
- Domain signals for the questions of section D: the signals column of the domain types catalogue, looked up in the code and the docs (calculation or rules code, authority names, entitlements per plan, analytics events).
- Only if the user names them: a Confluence space (Atlassian connector: pages tree) and Jira epics (JQL) to seed features and concepts. If the Atlassian connector is missing, guide the user to connect it (see **Connectors** in the conventions) or skip the seeding.

## 2. Build the design tree

The decisions that define the schema, each with the decisions that hang off it:

- Product name.
- For each preset type (`feature`, `process`, `concept`, `role`, `module`, `contract`, `integration`, `environment`, `decision`, `open-question`): keep / extend / drop. The preset's shape is the recommendation: on the functional side a glossary (`concept`), a feature catalogue grouped by `capability` (`feature`, generated as `functional/features/README.md`) and the roles; on the technical side **all and only** what the code cannot say (the **Derivability** rule in `writing.md`): never add technical fields or sections that restate the code. Keep `process` when users reach goals through flows across several features or roles, with hand-offs (workflows, approval chains in the code and docs); drop it otherwise. `decision` and `open-question` are system types: they can be extended, never dropped.
  - For kept types: extra fields, enum values (e.g. feature `status`, contract `kind`, environment `kind`), word budget (`max_words`), body sections.
  - Feature `capability` values: propose the functional areas found in the docs, the navigation of the frontend apps and the Confluence tree (e.g. "Invoicing", "Master data"), so the catalogue starts grouped.
- **Product domain** (section D): the domain types the product needs, from the catalogue or designed for it.
- Glossary languages (default `[en, it]`).
- Module map: which scan candidates are modules, their names, their `paths`, groupings.
- Thresholds in `brain.md` (archive, stale open questions, digest retention, context pack cap, raw cap).
- Review policy (`brain/.pb/schema/review.md`, the preset's template as the starting point): which changes need the area reviewers, asked on the PR that carries them (by CI on a code PR, by the routine on the brain PR).
  - Points of attention, once the types are settled: for each kept type, which changes need a human (any change, creation only, deletion, or only when given fields change, e.g. feature `status`, module `paths`). Recommend the preset's `watch` rules adapted to the kept and added types.
  - Confidence: below which level the writer's own rating flags a change (`direct_min_confidence`: `high` recommended; `medium` for a team that wants fewer reviews; `low` never flags by confidence).
  - Noise: whether pages still carrying a noise warning are flagged for review (`noise_to_review`, recommended `true`).
  - Reviewers per area: who reviews **technical** changes (modules, contracts, environments, technical decisions), **functional** ones (features, processes, concepts, functional decisions) and **design** ones (`ux` decisions); GitHub users or `org/team`. Recommend from the reviewer candidates. Cross-cutting pages (open questions without area) ask every area.
- Sources to register now or later via `/pb:routine-setup` (Teams channels, Confluence spaces, Jira projects the brain reads).
- **GitHub** (section G).
- **Commit rules** (section C).
- Bootstrap scope: which modules, specs and ADRs to turn into pages now.
- Existing documentation (section 6b): ingest all of it (recommended), only some groups, or none. Asked once the types are settled, since it is ingested into the chosen schema.

## 3. Grill in rounds

Interview the user relentlessly until the schema is fully settled. Work the tree in rounds:

- The **frontier** is every decision whose prerequisites are settled. Ask the whole frontier in one round (several `AskUserQuestion` calls if it has more than 4 questions); a question that depends on another open question waits for a later round.
- Ask as **How to ask** says: the recommended answer, derived from the preset and the facts you gathered, is the first option.
- After each answer, recompute the frontier. Facts are your job: if a question needs a fact from the repo or connectors, look it up instead of asking.
- Stop when the frontier is empty: every branch visited, nothing silently assumed.

## D. Product domain

The functional part beyond glossary, features and roles depends on the domain: settle it with the user, never by default.

1. **Ask about the domain**, in one round, with the questions of the **Interview** in `BASE/../../presets/domain-types/README.md` (who uses it and for what, rules, regulation, commercial shape, measures). Each question carries the signals you found (e.g. "the repo has `services/tax/` and the docs cite the Agenzia delle Entrate…") and its recommended answer, derived from them; skip the questions the facts already answer, and say what you assumed.
2. **Propose the domain types** that the answers call for, in one `AskUserQuestion` (`multiSelect`): one option per type, each with what it would hold for *this* product and an example page title drawn from the docs (e.g. `rule` → "Invoice totals are rounded per line"), the type's frontmatter as a `preview`. A need the catalogue does not cover becomes a new type designed in the same format (`applies_to` towards what it governs). Recommend only types with a clear recurring need; none is a valid answer.
3. For each chosen type, the follow-up decisions join the frontier: fields and enum values for this domain, budget, and the `watch` rules (e.g. a `regulation` page always reviewed by the functional reviewers).

## G. GitHub

Collect the facts first, never ask what `gh` can tell: the product's CI (`PB scan` → `ci`) and the rules on the default branch (`gh api repos/<repo>/rules/branches/<default>`). Then, in one round:

1. **Product pipelines.** Brain pages arrive in ordinary PRs: a PR that touches only `brain/` has nothing for the product's build to check. For each GitHub Actions workflow of the product that runs on `pull_request` without `paths-ignore`, offer (`multiSelect`, the edit as a `preview`) to add `paths-ignore: ["brain/**"]` under `pull_request`; never add it to a workflow whose jobs are **required** checks on the default branch (a PR touching only `brain/` would wait for a check that never runs): leave those as they are. Pipelines outside GitHub Actions: give the exact instructions, do not edit them.
2. **Required checks.** Recommend making `validate` and `brain-only` (from `pb-validate`) required on the default branch: they run on every PR and pass when no brain page changed, so code PRs are never blocked. `review` only informs and is not worth requiring.

The checks about `docs/brain` (who may push to it) belong to `/pb:routine-setup`.

## C. Commit rules

Every commit pb makes and the titles of its PRs must pass the repo's commit rules. Read what `PB scan` reports under `commit_rules`: open the commitlint configs, hooks and PR checks it lists, and look at `recent_subjects`. Nothing listed and nothing in the subjects: keep the defaults and do not ask. Otherwise propose, in one round, `commit_format` (only `{skill}` and `{summary}`, written quoted, e.g. `"docs(brain): {summary}"`), `pr_title_brain`, `pr_title_init` and, when the rules ask what a format cannot say (maximum length, ticket reference, sign-off), `commit_rules`; each with an example message.

## 4. Confirm

Show the final schema in one block in the chat: types table (area, folder, fields, budget; domain types marked as such), thresholds, glossary languages, review policy (watched points, confidence threshold, reviewers per area), module map, bootstrap scope, documentation to ingest (groups, files, words), GitHub changes (applied now or for an admin) and workflow edits. Then one `AskUserQuestion`: confirm / change something / stop. Do not write anything before it.

## 5. Scaffold and apply the schema

1. Temporary worktree from the default branch, so the user's checkout is never touched: `git fetch -q origin`, then `git worktree add -q --detach <tmp> origin/<default>`. Run every following command and edit every file there.
2. `PB scaffold --repo <tmp> --product "<name>"` (creates `brain/`, the `pb-validate` workflow, `brain/.gitattributes`, the CLAUDE.md pointer, the shared `.claude/settings.json` that enables the plugin for every clone, vendored toolkit). Report `skipped` workflows if any already existed, and check them against the templates.
3. Apply the interview results by editing `<tmp>/brain/.pb/schema/brain.md` (with the commit settings of section C), `review.md` and `types/*.md`. In `review.md` set `watch`, `direct_min_confidence`, `noise_to_review` and `reviewers`; check each handle with `gh api users/<login>` or `gh api orgs/<org>/teams/<slug>`, and keep the prose in sync with the rules. For the types: add/remove fields and enum values, set budgets, rewrite prose so it says when to create, when not to, body structure and budget. Delete dropped non-system type files; copy the domain types chosen in section D from `BASE/../../presets/domain-types/<type>.md` and adapt them; add new type files in the same format.
4. `PB --brain <tmp>/brain validate` must pass on the empty brain.

## 6. Bootstrap content

Propose, as one numbered list, the initial pages:
- one `module` per confirmed module, with `paths` and a 2–4 line `## Responsibility` drawn from its README and the docs: what it owns and what it does not; add `## Invariants`, `## Pitfalls` or `## Direction` only from a source that says them (docs, ADRs), never from reading the code — what the code says stays out;
- one `integration` per external system found (section 1), with `used_by` and `provider`, and only the behaviour the docs record;
- `role` pages for the user roles the docs and the frontend apps name;
- one `contract` per spec worth a page (`spec_path` set, `provided_by` the owning module);
- one `decision` (`area: technical`, `status: accepted`) per existing ADR, summarised and linked to the ADR file — never copied;
- optionally `feature`, `process` and `concept` pages from the Confluence space and the Jira epics the user named, with the epic keys in the features' `jira`.

Ask with `AskUserQuestion` (`multiSelect`, one option per group of pages: modules, contracts, integrations, roles, decisions, features, processes and concepts; "none" is the empty selection). Write them under `<tmp>/brain`, applying the significance gate and the writing rules; prefer fewer, accurate pages.

## 6b. Ingest the existing documentation

Skip when the discovery of section 1 found nothing worth ingesting; say so in one line.

1. **Ask.** One `AskUserQuestion`, with the facts in the question: "The repo has <N> documentation files (<W> words) in <G> groups: <group (files)>, … Ingest all of it into the brain now, following the schema we just agreed?". Options: **Ingest all (Recommended)** · **Choose the groups** · **Not now** (later with `/pb:put <folder>`). On "Choose the groups", a second `multiSelect` question, one option per group (more than 4 groups: by top folder, or several calls).
2. **Read and analyse**, group by group, one file at a time, with the schema of section 5 (the types in `<tmp>/brain/.pb/schema/types/`). Apply the **Analyse** rules of `/pb:put` (`BASE/../put/SKILL.md`, section 3) to each file:
   - extract features (with their `capability`), processes, concepts, roles, modules, contracts, integrations, environments, decisions, open questions and the pages of the domain types chosen in section D (rules, regulations…); route each item to the type whose prose says it belongs there;
   - apply **Derivability** (`writing.md`) to every technical statement: architecture docs often list structure, dependencies and endpoints that the code already says — drop those lines and keep the reasons, the boundaries, the invariants and the pitfalls;
   - the significance gate holds: setup steps, how-tos for running the code, changelogs and plans of finished work are dropped; implementation plans keep only the decisions they record;
   - **merge, never duplicate**: resolve each entity with `PB --brain <tmp>/brain resolve` against the pages already written (section 6 and earlier files); a module README enriches the module page, an ADR already turned into a decision is not ingested twice;
   - the doc stays authoritative in the repo: summarise and link it, never copy it; cite it inline and in `sources` as `repo:<path>`; do not capture it in `.pb/raw/`, it is already versioned;
   - check claims that the code can contradict (module boundaries, endpoints, names) against the code; a contradiction, or two docs that disagree, becomes an `open-question` citing both, never a silent pick. A doc not changed for over a year while the code it describes changed since (`git log -1 --format=%cs -- <module paths>`) is a weak source: say so in the page and prefer an `open-question` for its doubtful claims.
   With many files (more than ~30, or over ~50,000 words), you may hand each group to a subagent with `writing.md`, the schema files and these rules: it returns proposed changes (page · create/update · content · sources), it writes nothing; you merge the proposals and resolve overlaps.
3. **Plan.** Show the list of pages to create or update, grouped by type, each with the docs it comes from, plus the files that gave nothing and why (one line per group). Confirm with one `AskUserQuestion`: write all / change something / skip.
4. **Write** under `<tmp>/brain`, following each type's prose and budget, then `PB --brain <tmp>/brain validate`: fix every error before going on.

## 7. Close

1. `PB --brain <tmp>/brain message --skill init -m "create brain for <product>"`: its `message` is the init commit, its `pr_title_init` the PR title. Commit in the temporary worktree: `PB --brain <tmp>/brain commit --raw -m "<message>" --allow-default --include CLAUDE.md .claude/settings.json .github/workflows/pb-validate.yml` (leave out the workflow if it was reported as `skipped`). Then the generated files: `PB --brain <tmp>/brain generate`, `PB --brain <tmp>/brain commit --skill generate -m "refresh generated files" --allow-default`. With `rejected`, as in the closing flow of `writing.md`: the same command with `--raw -m "<message>"`, every other argument (`--include …`) unchanged; then correct the settings of section C.
2. Push the branch: `git -C <tmp> push -q origin HEAD:refs/heads/pb/init`.
3. Open the PR: `gh pr create --head pb/init --base <default> --title "<pr_title_init>" --body <what it brings: the brain, the pb workflow, the CLAUDE.md pointer and the plugin settings; merging it turns the workflow on for every later PR>`. The product pipeline edits of section G are code: put them in a separate branch and PR towards the default branch, never in this PR.
4. `git worktree remove --force <tmp>`. The user's checkout is untouched; the brain reaches it once the PR is merged and they bring the default branch into their branch (`git pull`, or merge the default branch). Check then that it reads: `PB version` returns the brain.

Then explain the next steps, in a few lines:
- what the documentation ingestion brought in (pages per type, files skipped), and how to ingest more later (`/pb:put <path>`);
- merge the init PR to start; after that, developers write pages in their working branch with the `pb` skills and commit them with the code, and CI checks that the generated files are fresh and tells the area reviewers about watched points;
- newcomers run `/pb:setup` (tools, GitHub login, clone);
- GitHub settings left to an admin, if any, as a checklist;
- `/pb:routine-setup` to feed the brain nightly from Teams, Confluence and merged PRs: the routine writes on `docs/brain` and keeps one PR open, and `/pb:merge` brings its changes to the default branch;
- Cowork users read the brain on the default branch through the GitHub connector.

## U. Upgrade an existing brain

A brain of the current format whose vendored toolkit is older than the plugin gets the current `pb-validate` workflow, toolkit and `AGENTS.md` writing rule through an ordinary PR. Say in plain words what changes and ask to confirm. Before it, the open brain PR from `docs/brain` should be merged: say so if one is open. Then:

1. Run sections G (GitHub) and C (commit rules).
2. Temporary worktree from the default branch (as in section 5), `PB scaffold --repo <tmp> --upgrade` (rewrites `pb-validate`, writes `brain/.gitattributes`, deletes retired workflows, enables the plugin, refreshes the toolkit and the writing rule in `brain/AGENTS.md`; the result lists what it removed in `deleted`); write the settings of section C to `<tmp>/brain/.pb/schema/brain.md`. Commit with `PB --brain <tmp>/brain commit --skill init -m "upgrade the project brain" --allow-default --include .claude/settings.json .github/workflows/pb-validate.yml`, adding every path of `deleted`; then `PB --brain <tmp>/brain generate`, `PB --brain <tmp>/brain commit --skill generate -m "refresh generated files" --allow-default`, and steps 2–4 of section 7 (branch `pb/init`, a title that satisfies the PR rules found in section C, e.g. the prefix of `pr_title_init` followed by "upgrade the project brain").
3. Tell the user to run `/pb:routine-setup` again once the PR is merged: it updates the routine's prompt.

A brain in the format of an earlier pb version is never upgraded: `PB scaffold` stops with `code: old-format`. Relay its message: remove `brain/` and create it again with `/pb:init`.
