# Writing conventions of the `pb` skills

Read by every skill that writes to the brain, after `conventions.md`.

## Before writing

Routine runs skip this paragraph (see **Modes** in the conventions). Otherwise `PB workspace sync`: write every file under its `brain` (BRAIN), never in the user's checkout. If it reports:
- `leftovers`: pages written earlier and never saved, maybe by another session. Show them in one line and ask: save them with this work, or discard them (`git -C <worktree> reset -q -- brain`, `git -C <worktree> checkout -- brain`, `git -C <worktree> clean -fdq brain`). Never drop them silently.
- `rebase_in_progress`: a save stopped on a conflict; finish it first (**Conflicts** below).
- `unpushed`: saves that did not reach GitHub (offline); the next `PB save` sends them, nothing to do.

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

Every writing operation ends like this:

1. `PB validate <created or changed pages>`. Fix errors and repeat, at most twice. If errors remain, stop and report them; do not save broken pages.
2. Condense every page with an `over-budget` warning and fix every noise warning (below), then validate again.
3. `PB save -m "pb(<skill>): <one-line summary>" <every file this work created, changed or deleted>`: pages, and also `raw/` extracts, `.pb/state/*.json` (cursors, suppressions), `.pb/corrections.md`, `schema/proposals.md`; plus leftovers the user chose to save. Every skill's closing flow means this list, even when it shows only the message. It commits, regenerates index and context packs, pushes straight to `docs/brain` and returns at once; never wait for CI. Pages the review policy holds, and changes to `schema/` or the toolkit, go to a review PR (`review.pr`).
4. Tell the user the outcome in plain words, without git terms: "Saved: everyone sees it now." When `review` is set: "These pages wait for a review by <reviewers>: <link>." When `pushed` is false with `unpushed` > 0: "Saved on this computer; it goes out with the next save (no connection now)." Then the `problems`, if any, in one line each.
5. Exit 1 with `errors`: fix those pages and save again. Exit 1 with `conflict`: **Conflicts** below.
6. Summarise: pages created/updated (as `[[links]]`), open questions raised, anything dropped by the significance gate worth mentioning.

Routine runs use their own closing flow (`templates/routine/prompt.md`, `/pb:routine-run`).

## Conflicts

Someone saved the same page in the meantime. `conflict.paths` lists the files, with `<<<<<<<`, `=======`, `>>>>>>>` markers. Resolve them yourself, never ask the user to use git: merge both versions into one coherent page (keep every fact, drop duplicates, the newer source wins on a contradiction; a real disagreement becomes an `open-question`), remove the markers, then `PB save --continue`. Mention it in one line: "Someone had changed <page> meanwhile: I merged both versions." If the merge needs a judgement only the user can make, ask before continuing.

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

Fix them before saving. A warning that is a false positive can stay: in interactive saves the user's confirmation lets it through; in routine runs, with `noise_to_review: true` in `brain/schema/review.md`, the page waits for a reviewer.

## Confidence and review

`brain/schema/review.md` decides which changes reach the branch directly and which wait in a PR, by the points of the schema they touch (`watch`) and by how sure the writer is. Rate every page you create or update:
- **high**: stated explicitly and settled in the source;
- **medium**: inferred, or from one voice in a discussion that did not visibly conclude;
- **low**: an interpretation, an ambiguous name resolution, a contradiction, a type chosen with doubt.

Only the routine passes ratings to the toolkit (`--confidence PATH=LEVEL`, high is the default). In interactive skills the user is there: show what you rated medium or low in the plan or preview and let them decide; once they confirm, the page counts as high. Pages on points watched by the policy go to a review PR whatever the confidence.

## Schema signals

When the schema does not fit (the same structure repeated in a generic type, a missing field, recurring `unknown-field` warnings), append a line to `brain/schema/proposals.md`: `- [ ] P<n> · <proposal>` with `n` = highest existing + 1. `/pb:schema` applies proposals. `proposals.md` is under `schema/`: saving it opens a review PR, which is how proposals reach the maintainers.
