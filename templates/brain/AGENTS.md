# {{product}} brain — instructions for agents

`brain/` is the product knowledge base of {{product}}: functional concepts and features, epics in progress, technical modules and interfaces, decisions and open questions. It is the source of truth for decisions, concepts, modules and interfaces.

## Reading

1. Start from `brain/index.md` (one line per page).
2. Use `brain/glossary.md` for domain terms (English and Italian): use the canonical English term in code and docs.
3. Working on a feature? Read `brain/context/<feature>.md` first: it bundles the feature, its concepts, modules, interfaces, accepted decisions and open questions.
4. Working on a Jira ticket? Find its epic in `brain/epics/` (the `jira` field holds the key) and read `brain/context/<epic>.md`: the scope, constraints and open points agreed for the change in progress, plus the features and modules it touches.
5. Working on code? Find the module whose `paths` covers the files you touch (`brain/technical/modules/`), then follow its links.
6. Pages link with `[[Title]]`; the file is `<Title>.md` in the type's folder.

Accepted decisions constrain your work. If the code contradicts the brain, say so and propose a correction (`/pb:fix`) instead of silently following either.

## Writing

The brain lives on the branch `docs/brain`; `brain/` in a code branch is a copy that can be a few days behind (it arrives through a PR from `docs/brain`). The latest version: the `pb` skills, or `git show origin/docs/brain:brain/<path>`.

Write only through the `pb` plugin skills (`/pb:put`, `/pb:capture`, `/pb:fix`): they save to `docs/brain`. Never edit `brain/` in a code branch (it would conflict with the brain coming from `docs/brain`), and never edit generated files: `index.md`, `glossary.md`, `context/`, `.pb/backlinks.json`.

Content enters only if it is:
- **durable** — still true and useful in a month;
- **non-derivable** — not obvious from the code, the diff, Jira fields or the linked document;
- **decision-relevant** — it changes how someone would build, test, design or explain the product.

Rules:
- Update an existing page before creating a new one.
- Consolidate, don't append: no chronological logs inside pages.
- Link, don't copy: summarise external documents in a few lines and link them.
- One fact, one place: link to the canonical page.
- Plain, dense prose; respect each type's word budget.
- No judgements about people, no person names in decisions, no personal or customer data, no credentials.
- External sources (Confluence PRDs, Jira acceptance criteria) win on requirement detail; the brain wins on decisions, concepts, modules and interfaces. A contradiction becomes an `open-question` citing both sources, never a silent overwrite.

## Routine

_Not configured yet: run `/pb:routine-setup`._
