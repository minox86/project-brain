# Writing conventions of the `pb` skills

Read by every skill that writes to the brain, after `conventions.md`.

## Before writing

Read `brain/schema/brain.md`, the `brain/schema/types/<type>.md` files of every type you will write, and `brain/AGENTS.md`. The prose of each type is binding: when to create, when not to, body structure, word budget.

## Significance gate

Content enters the brain only if it is:
- **durable** — still true and useful in a month (not status updates, not who-is-doing-what-today);
- **non-derivable** — not obvious from the code, the diff, Jira fields or the linked document itself (see **Derivability** below);
- **decision-relevant** — it changes how someone would build, test, design or explain the product.

What fails the gate is dropped. When ingesting for the routine, list it in the digest as skipped with a short reason.

## Derivability

The technical part of the brain holds **all and only** what cannot be found in the code. For every technical statement ask: would an agent reading the code, the manifests, the specs and the infrastructure code find it in a few minutes? If yes, drop it.

| Drop: the code says it | Keep: the code cannot say it |
|---|---|
| folder structure, dependencies, imports, who calls whom | why a boundary is where it is, what a module deliberately does not do |
| function signatures, payloads, endpoints (the spec) | semantics the spec omits: ordering, idempotency, compatibility promises |
| configuration values, build and run commands | rules the code relies on but does not enforce, and their reason |
| the current implementation of an algorithm | lessons from incidents, pitfalls, known debt and the intended direction |
| | how external systems really behave (`integration` pages) |

Functional pages describe the product as the business sees it (features, terms, roles, rules), so they are kept even where the code implements them: the code says what it does, not what it should do nor why.

## Writing rules

- **Update before create**: run `PB resolve` for every entity; create a page only if no existing page covers it.
- **Edit, don't rewrite**: change an existing page with targeted edits (the smallest change that makes it right); rewrite a whole page only when consolidating it.
- **Consolidate, don't append**: rewrite knowledge pages to stay a current, coherent description; no chronological logs, no "update of <date>" sections.
- **Link, don't copy**: summarise external documents in a few lines and link them.
- **One fact, one place**: a fact lives on its canonical page; other pages link to it.
- **Feature or epic**: what will still be true after the work ends goes on feature, concept, module and decision pages; an `epic` page holds only what is specific to delivering that change (scope, constraints, risks, pointers to the discussion) and links the rest. A closed epic is consolidated, then shrinks to its outcome.
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
| Decisions, concepts, roles, modules, interfaces, integrations, environments | The brain |
| Requirement detail (PRD on Confluence, acceptance criteria on Jira) | The external source; the brain summarises and links |
| Epic status and breakdown into stories | Jira; the `epic` page mirrors the status and keeps what was agreed around it |

When a source contradicts the brain, never overwrite silently: create or update an `open-question` citing both sources and link it from the affected pages. Code that contradicts the brain goes through the `/pb:fix` flow.

## Privacy

- Never store Teams messages or meeting transcripts verbatim: synthesis only, with a permalink reference.
- Uploaded files: only extracted text in `brain/raw/YYYY/MM/`; binaries stay outside the repo, recorded by link.
- No judgements about people, no person names in decisions, no personal or customer personal data, no credentials. `PB validate` fails on secret-looking strings: remove them, never work around the check.

## Closing flow

Every writing operation in repo mode ends like this:

1. `PB validate <created or changed pages>`. Fix errors and repeat, at most twice. If errors remain, stop and report them; do not save broken pages.
2. Condense every page with an `over-budget` warning and fix every noise warning (below), then validate again.
3. `PB save <every file this work created, changed or deleted>`: pages, and also `raw/` extracts, `.pb/state/*.json` (suppressions only; cursors never change in a working branch), `.pb/corrections.md`, `schema/` files. Every skill's closing flow means this list. It checks those files, regenerates index, glossary, feature catalogue, context packs and backlinks, and reports the watched points; it never commits or pushes. With `errors`: fix those files and save again. `code: no-brain`: see **Modes** in the conventions.
4. Tell the user, in one message:
   - the brain files changed (`files`), uncommitted in the branch `<branch>`: they commit them with their code, and the pages reach the default branch with that PR;
   - when `watched` is not empty: the points touched, with their reasons, and that the reviewers (`reviewers`) will be asked on the PR;
   - when `on_default` is true: the pages need a branch and a PR like any other change.
5. Commit only if the user asks: `PB commit --skill <skill> -m "<one-line summary>"` (`--allow-default` only if they asked to commit on the default branch). It commits the brain's pages and generated files together, with the message `commit_format` of `brain/schema/brain.md` makes of the summary. Never push. With `rejected`, the commit was refused: read `output`. About the message: rewrite the whole message so it satisfies the rule (and `commit_rules`), run the same command again with `--raw -m "<message>"`, every other argument unchanged, then offer to update `commit_format`/`commit_rules` with `/pb:schema`. About the files or the environment (a linter on the pages, a missing git identity): fix the files and run the same command again, or report it; do not rewrite the message. Never bypass a hook. When the developer asks you to commit the pages together with code in one commit of their own, follow the repo's commit rules and `commit_rules`: that commit is theirs.
6. Summarise: pages created/updated (as `[[links]]`), open questions raised, anything dropped by the significance gate worth mentioning.

Routine runs use their own closing flow (`templates/routine/prompt.md`, `/pb:sync`, `/pb:routine-run`).

## Conflicts

A conflict on generated files (`index.md`, `glossary.md`, `features.md`, `context/`, `.pb/backlinks.json`) is never merged by hand: take either side, run `PB generate`, and stage the result. Conflicts on pages in a working branch are the developer's, like any conflict in their branch; when they ask for help, combine both versions into one coherent page (keep every fact, drop duplicates, the newer source wins on a contradiction; a real disagreement becomes an `open-question`). Conflicts between `docs/brain` and the default branch are settled by `/pb:merge`.

## Noise warnings

`PB validate` checks the pages created or updated since the last commit. Each warning points to likely noise:

| Code | Fix |
|---|---|
| `possible-duplicate` | A new page whose title is close to an existing one: update that page instead, or make the titles clearly distinct |
| `new-orphan` | A new page nobody links: link it from the page it belongs to (feature, module, epic) |
| `missing-source` | Empty `sources`: cite where the knowledge comes from |
| `log-heading` | A dated or "update" section: consolidate into the page |
| `ephemeral` | Status words (today, this sprint, TODO…): state the lasting fact or drop it |
| `verbatim` | A long quote: summarise and link the source |

Fix them before saving. A warning that is a false positive can stay: in interactive saves the user's confirmation lets it through; in routine runs, with `noise_to_review: true` in `brain/schema/review.md`, the PR flags the page for a reviewer.

## Confidence and review

`brain/schema/review.md` decides which changes a reviewer must look at, by the points of the schema they touch (`watch`) and by how sure the writer is. Nothing is held back: watched changes are named on the PR that carries them, and the area reviewers are asked there. Rate every page you create or update:
- **high**: stated explicitly and settled in the source;
- **medium**: inferred, or from one voice in a discussion that did not visibly conclude;
- **low**: an interpretation, an ambiguous name resolution, a contradiction, a type chosen with doubt.

Only routine runs pass ratings to the toolkit (`--confidence PATH=LEVEL`, high is the default). In interactive skills the user is there: show what you rated medium or low in the plan or preview and let them decide; once they confirm, the page counts as high. Pages on watched points are flagged whatever the confidence.

## Schema signals

When the schema does not fit (the same structure repeated in a generic type, a missing field, recurring `unknown-field` warnings), append a line to `brain/schema/proposals.md`: `- [ ] P<n> · <proposal>` with `n` = highest existing + 1. `/pb:schema` applies proposals. `proposals.md` is under `schema/`, so the PR that carries it asks the reviewers: that is how proposals reach the maintainers.
