---
name: open-question
area: cross
folder: open-questions
max_words: 200
system: true
fields:
  area: {kind: enum, values: [functional, ux, technical]}
  status: {kind: enum, values: [open, resolved, dropped], default: open}
  resolved_by: {kind: link, to: decision}
  affects: {kind: list, of: link}
required: [area]
---
# Open question

A question that blocks or shapes a decision and has no answer yet, or a contradiction between sources that someone must settle.

**Create** a page when a question is raised and left unanswered, or when ingestion finds two sources that disagree (cite both).

**Close** it with `status: resolved` and `resolved_by` pointing to the decision that answers it, or `dropped` with one line on why.

**Body structure:**
- The question in one sentence.
- `## Why it matters` — what it blocks.
- `## Known so far` — facts and positions, with sources.

Keep it under 200 words.
