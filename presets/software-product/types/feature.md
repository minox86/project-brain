---
name: feature
area: functional
folder: functional/features
max_words: 600
fields:
  status: {kind: enum, values: [idea, planned, in-progress, released, deprecated], default: idea}
  jira: {kind: list, of: string}
  modules: {kind: list, of: link, to: module}
  concepts: {kind: list, of: link, to: concept}
  figma: {kind: string}
required: []
---
# Feature

A user-facing capability of the product: what it lets a user do and how it is expected to behave.

**Create** a page when a capability has a recognised name and is discussed, specified or built across more than one conversation, document or ticket.

**Do not create** a page for a single story, a bug or a UI tweak: those live in Jira. Fold them into the feature they belong to only if they change its expected behaviour.

**Body structure:**
- `## Purpose` — the user problem it solves, in 1–3 lines.
- `## Expected behaviour` — rules, states, edge cases, as bullets. This is what QA tests against.
- `## UX notes` — key interaction choices; link the `decision` pages that made them.
- `## Out of scope` — what it deliberately does not do.

Link requirements (`jira`, Confluence PRD) instead of copying them. Keep it under 600 words.
