---
name: ask
description: Answers questions about the product from the project brain — features, processes, domain concepts, modules, contracts, decisions and their reasons, open questions — with citations to brain pages and sources. Works in Claude Code on the brain of the current branch and, read-only, in Cowork on the default branch through the GitHub connector. Use for questions like "why did we decide X?", "what does Y mean?", "which module handles Z?", "what is still open on W?".
argument-hint: "<question>"
---

# /pb:ask — answer from the brain

Question: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Works in repo mode and read mode. In Cowork without a GitHub connector that reads the monorepo, guide the user to connect it (see **Connectors** in the conventions) before answering: never answer about the product from memory.

1. Read `brain/README.md`, then the `README.md` of the folders that matter: the glossary `brain/functional/concepts/README.md`, the catalogue `brain/functional/features/README.md` for questions about what the product does (in read mode, from the monorepo's default branch through the GitHub connector).
2. Pick the relevant pages from those lists; for a feature read `brain/.pb/context/<title>.md` first; for code paths use `PB context --paths` (repo mode).
3. Follow links (relative to the file that holds them) only as far as needed. Prefer accepted decisions over superseded ones; mention open questions that affect the answer.
4. Answer concisely, in the user's language. Cite every claim with a Markdown link to the page's repo path (`[Invoice](brain/functional/concepts/Invoice.md)`) and, when useful, its external source (`jira:…`, `confluence:…`, `gh:pr/…`).
5. If the brain does not know: say so plainly. In repo mode you may look at the code or the external source to answer, but label that part as "not in the brain" and suggest `/pb:put` (or `/pb:capture`) to record it.
6. If the brain contradicts the code or a source you checked, say so and suggest `/pb:fix`.

Never write to the brain from this skill.
