# Shared conventions of the `pb` skills

Every `pb` skill reads this file before acting. BASE is the skill's base directory, shown when the skill loads; the plugin root is `BASE/../..`.

## Toolkit

    PB = python3 "BASE/../../scripts/pb.py"

(`${CLAUDE_PLUGIN_ROOT}/scripts/pb.py` is the same file.)

- Every command prints one JSON object. Exit `0` ok; `1` findings described in the JSON; `2` usage or environment error (read `error`).
- Run from anywhere inside the monorepo; the brain is found by walking up to `brain/schema/VERSION`. Otherwise pass `--brain <dir>` or set `PB_BRAIN`.
- Never do by hand what the toolkit does: validation, name resolution, context packs, stats, lint, sync cursors, commits.

| Command | Use |
|---|---|
| `PB version` | `brain` is the brain path, or `null` outside a brain |
| `PB validate [paths…]` | Check pages against the schema, secrets, budgets (warnings never fail) |
| `PB resolve "<name>" [--type T]` | Candidate pages for a name (`title`, `alias`, `partial`, `fuzzy`) |
| `PB context (--jira KEY \| --feature T \| --paths P…) [--max-words N]` | Context pack: pages + markdown |
| `PB stats` | Pages and words per type/area, over-budget pages, largest pages |
| `PB lint` | Structural findings (validate errors, budgets, duplicates, orphans, stale, archivable, dead module paths, superseded references) |
| `PB state get <source> [key]` / `PB state set <source> <key> <json>` | Sync cursors (`teams`, `confluence`, `github`, `jira`) |
| `PB state suppress <source> "<claim>"` | Claim corrected by `/pb:fix` that sync must not re-ingest |
| `PB correction --page P --wrong W --right R --evidence E` | Append to `brain/.pb/corrections.md` |
| `PB commit -m MSG [--allow-default]` | Commit `brain/` changes (generated files excluded) on the current branch |
| `PB routine start --branch B` / `PB routine finish --branch B -m MSG` | Routine runs: checkout target branch; commit, rebase, push (no PR) |
| `PB scan [--repo DIR]` | Facts about the monorepo for bootstrap |
| `PB scaffold --product NAME [--repo DIR]` | Create `brain/`, CI workflows, CLAUDE.md pointer, vendored toolkit |
| `PB generate` | CI only: index, glossary, context packs, backlinks, digest retention |
| `PB toolkit-sync` | Refresh `brain/.pb/toolkit` after a plugin upgrade |

## Modes

Run `PB version` first.

- **Repo mode** — `brain` is a path: all skills available. You are in the monorepo (Claude Code).
- **Read mode** — `brain` is `null` or Python is unavailable, but a GitHub connector or tool can read the monorepo: only `/pb:ask` and `/pb:context`. Read files from the default branch: `brain/index.md` first, then `brain/glossary.md`, `brain/context/<feature>.md`, and the pages they link. Never try to write.
- **Neither** — say that the brain is not reachable: open the monorepo in Claude Code, or connect GitHub with read access to the monorepo in Cowork.

In read mode, write skills (`put`, `meeting`, `capture`, `fix`, `sync`, `lint`, `schema`, `init`, `routine-setup`) do not run. Reply: "The brain is read-only here. Knowledge reaches it through the Teams channels and Confluence spaces the nightly routine reads; a developer can also add it with `/pb:put` or fix it with `/pb:fix`."

## Before writing

Read `brain/schema/brain.md`, the `brain/schema/types/<type>.md` files of every type you will write, and `brain/AGENTS.md`. The prose of each type is binding: when to create, when not to, body structure, word budget.

## Page format

- File name = `title` + `.md`, in the type's `folder`. Titles are unique across the brain and cannot contain `\ / : * ? " < > | # ^ [ ]`.
- Wikilinks always point to the canonical title: `[[Invoice]]`, or `[[Invoice|invoices]]` to display other text. In frontmatter quote them: `provided_by: "[[Billing]]"`, `affects: ["[[A]]", "[[B]]"]`.
- Implicit fields for every type: `type`, `title`, `aliases`, `summary` (one line, shown in the index), `created`, `updated`, `sources`.
- Dates are ISO `YYYY-MM-DD`; convert relative expressions against the date of the source.
- Quote frontmatter strings containing `, ` `: ` ` #` or starting with a symbol.
- External references: `jira:<KEY>`, `confluence:<SPACE>/<pageId>`, `teams:<team>/<channel>/<messageId>`, `teams:meeting/<id>`, `gh:pr/<n>`, `gh:issue/<n>`, `figma:<fileKey>/<nodeId>`, `url:<url>`, `raw:<path without .md>`.
- Relevant claims cite their source inline `^[jira:FIN-412]`; the same references go in `sources`.
- Never write a field you cannot infer with reasonable confidence: omit it.

## Significance gate

Content enters the brain only if it is:
- **durable** — still true and useful in a month (not status updates, not who-is-doing-what-today);
- **non-derivable** — not obvious from the code, the diff, Jira fields or the linked document itself;
- **decision-relevant** — it changes how someone would build, test, design or explain the product.

What fails the gate is dropped. When ingesting for the routine, list it in the digest as skipped with a short reason.

## Writing rules

- **Update before create**: run `PB resolve` for every entity; create a page only if no existing page covers it.
- **Consolidate, don't append**: rewrite knowledge pages to stay a current, coherent description; no chronological logs, no "update of <date>" sections.
- **Link, don't copy**: summarise external documents in a few lines and link them.
- **One fact, one place**: a fact lives on its canonical page; other pages link to it.
- **Plain, dense prose**: no preambles, no restating the title, no filler; bullets over paragraphs.
- **Budgets**: respect each type's `max_words`. An `over-budget` warning from validate means: condense that page before committing.
- **Decisions are never rewritten** because things changed: create a new decision with `supersedes` and set the old one to `superseded`.
- **Propagation**: a decision that changes stable knowledge also updates the affected feature/module/interface page and links to it.

## Name resolution

For every entity mentioned run `PB resolve "<name>"`:
- a `title` or `alias` match is the page: use it;
- one `partial` candidate and nothing else above 0.5: use it;
- several candidates, or only `fuzzy`: ask the user one multiple-choice question including "new page"; then add the name used to the chosen page's `aliases`;
- no candidate: a new entity; create it only if the type's prose allows, else write the name as plain text.

## Authority and conflicts

| Fact | Source of truth |
|---|---|
| Decisions, concepts, modules, interfaces, environments | The brain |
| Requirement detail (PRD on Confluence, acceptance criteria on Jira) | The external source; the brain summarises and links |

When a source contradicts the brain, never overwrite silently: create or update an `open-question` citing both sources and link it from the affected pages. Code that contradicts the brain goes through the `/pb:fix` flow.

## Privacy

- Never store Teams messages or meeting transcripts verbatim: synthesis only, with a permalink reference.
- Uploaded files: only extracted text in `brain/raw/YYYY/MM/`; binaries stay outside the repo, recorded by link.
- No judgements about people, no person names in decisions, no personal or customer personal data, no credentials. `PB validate` fails on secret-looking strings: remove them, never work around the check.

## Closing flow (repo mode)

Every writing operation ends like this:

1. `PB validate <created or changed pages>`. Fix errors and repeat, at most twice. If errors remain, stop and report them; do not commit broken pages.
2. Condense every page with an `over-budget` warning, then validate again.
3. `PB commit -m "pb(<skill>): <one-line summary>"`. The commit stays on the current branch and travels with the developer's PR. Never push, never open PRs.
4. If the commit fails with `code: on-default-branch`, ask: "You are on `<branch>`. Create a working branch (recommended) or commit here?" Create the branch with `git switch -c <name>` and rerun, or rerun with `--allow-default`.
5. Summarise: pages created/updated (as `[[links]]`), open questions raised, anything dropped by the significance gate worth mentioning.

The nightly routine uses its own closing flow (see `templates/routine/prompt.md`).

## Schema signals

When the schema does not fit (the same structure repeated in a generic type, a missing field, recurring `unknown-field` warnings), append a line to `brain/schema/proposals.md`: `- [ ] P<n> · <proposal>` with `n` = highest existing + 1. `/pb:schema` applies proposals.
