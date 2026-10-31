# {{product}} brain — instructions for agents

`brain/` is the product knowledge base of {{product}}: functional concepts and features, technical modules and interfaces, decisions and open questions. It is the source of truth for decisions, concepts, modules and interfaces.

## Reading

1. Start from `brain/index.md` (one line per page).
2. Use `brain/glossary.md` for domain terms (English and Italian): use the canonical English term in code and docs.
3. Working on a feature? Read `brain/context/<feature>.md` first: it bundles the feature, its concepts, modules, interfaces, accepted decisions and open questions.
4. Working on code? Find the module whose `paths` covers the files you touch (`brain/technical/modules/`), then follow its links.
5. Pages link with `[[Title]]`; the file is `<Title>.md` in the type's folder.

Accepted decisions constrain your work. If the code contradicts the brain, say so and propose a correction (`/pb:fix`) instead of silently following either.

## Writing

Write through the `pb` plugin skills (`/pb:put`, `/pb:capture`, `/pb:fix`) or, by hand, following `brain/schema/types/<type>.md`. Never edit generated files: `index.md`, `glossary.md`, `context/`, `.pb/backlinks.json`.

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
