---
name: decision
area: cross
folder: decisions
area_folders: {functional: functional/decisions, ux: functional/decisions, technical: technical/decisions}
max_words: 400
system: true
fields:
  area: {kind: enum, values: [cross, functional, ux, technical]}
  status: {kind: enum, values: [proposed, accepted, superseded], default: accepted}
  date: {kind: date}
  supersedes: {kind: link, to: decision}
  affects: {kind: list, of: link}
  resolves: {kind: list, of: link, to: open-question}
required: [area]
---
# Decision

A choice the team made, functional, UX or technical, with its reasons. A lightweight ADR.

**Where it lives** follows its `area` (`area_folders`): a `technical` decision (architecture, stack, how a module or contract is built) in `technical/decisions/`, a `functional` or `ux` one (what the product does, how it behaves, how it is used) in `functional/decisions/`, a `cross` one in `decisions/`. `cross` is for a choice that binds both sides at once (scope of a release, a constraint on product and architecture together): when one side clearly owns it, give it that area. A decision whose area changes moves to the other folder.

**Create** a page when a choice constrains future work and someone could reasonably ask "why is it like this?". Title it with the outcome ("Invoices are approved by a single approver"), not the question.

**Do not create** a page for choices with no alternatives considered or that only affect one ticket.

**Never rewrite** an accepted decision because things changed: create a new decision with `supersedes` and set the old one to `superseded`. Correct it in place only when it was recorded wrongly.

**Do not name people.** Write what was decided and why, not who decided.

**Body structure:**
- `## Context` — the forces at play, 1–4 lines.
- `## Options` — the alternatives considered, one line each.
- `## Outcome` — the choice.
- `## Consequences` — what it implies for features and modules (link them in `affects`).

Keep it under 400 words.
