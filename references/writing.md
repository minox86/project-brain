# Writing conventions of the `pb` skills

Read by every skill that writes to the brain, after `conventions.md`.

## Before writing

Read `brain/schema/brain.md`, the `brain/schema/types/<type>.md` files of every type you will write, and `brain/AGENTS.md`. The prose of each type is binding: when to create, when not to, body structure, word budget.

## Significance gate

Content enters the brain only if it is:
- **durable** — still true and useful in a month (not status updates, not who-is-doing-what-today);
- **non-derivable** — not obvious from the code, the diff, Jira fields or the linked document itself;
- **decision-relevant** — it changes how someone would build, test, design or explain the product.

What fails the gate is dropped. When ingesting for the routine, list it in the digest as skipped with a short reason.

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
| Decisions, concepts, modules, interfaces, environments | The brain |
| Requirement detail (PRD on Confluence, acceptance criteria on Jira) | The external source; the brain summarises and links |
| Epic status and breakdown into stories | Jira; the `epic` page mirrors the status and keeps what was agreed around it |

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
