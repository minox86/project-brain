---
name: process
area: functional
folder: functional/processes
max_words: 500
fields:
  roles: {kind: list, of: link, to: role}
  applies_to: {kind: list, of: link}
  status: {kind: enum, values: [active, planned, retired], default: active}
required: []
---
# Process

An end-to-end business flow that crosses several features and roles: order-to-cash, employee onboarding, month-end close. It shows how the features fit together from the user's side.

**Create** a page when users reach a goal through several features in sequence, with hand-offs between roles, and the order or the hand-offs matter.

**Do not create** a page for a flow inside one feature (it is that feature's expected behaviour) nor for a technical pipeline (it is a module).

**Fields:** `roles` who takes part; `applies_to` the features (in order) and concepts the process goes through.

**Body structure:**
- Goal and outcome in 1–2 lines.
- `## Steps` — numbered: who does what, in which feature, and what moves the flow on; link features and concepts.
- `## Exceptions` — what happens when a step fails, is rejected or is skipped.
- `## Timing` — deadlines and periodicity, if any.

Keep it under 500 words.
