---
name: ask
description: Answers questions about the product from the project brain — features, domain concepts, modules, interfaces, decisions and their reasons, open questions — with citations to brain pages and sources. Works in Claude Code and, read-only, in Cowork through the GitHub connector. Use for questions like "why did we decide X?", "what does Y mean?", "which module handles Z?", "what is still open on W?".
argument-hint: "<question>"
---

# /pb:ask — answer from the brain

Question: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Works in repo mode and read mode.

1. Read `brain/index.md` and `brain/glossary.md` (in read mode, from the monorepo's default branch through the GitHub connector).
2. Pick the relevant pages from the index; for a feature read `brain/context/<feature>.md` first; for code paths use `PB context --paths` (repo mode).
3. Follow `[[links]]` only as far as needed. Prefer accepted decisions over superseded ones; mention open questions that affect the answer.
4. Answer concisely, in the user's language. Cite every claim with `[[Page]]` and, when useful, its external source (`jira:…`, `confluence:…`, `gh:pr/…`).
5. If the brain does not know: say so plainly. In repo mode you may look at the code or the external source to answer, but label that part as "not in the brain" and suggest `/pb:put` (or `/pb:capture`) to record it.
6. If the brain contradicts the code or a source you checked, say so and suggest `/pb:fix`.

Never write to the brain from this skill.
