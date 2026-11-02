---
name: role
area: functional
folder: functional/roles
max_words: 300
fields:
  kind: {kind: enum, values: [internal, customer, partner, system], default: customer}
  term_it: {kind: string}
required: []
---
# Role

Someone (or something) that uses the product with a recognisable goal: a persona, a user role, an external actor, an automated system acting on its own.

**Create** a page when the team talks about a kind of user by name and it changes how features behave or are designed (what they see, what they may do, what they care about).

**Do not create** a page for one customer or one person, nor for a technical account.

**Fields:** `kind` internal staff, customer user, partner, or system; `term_<lang>` the name in the other glossary languages. Put other names in `aliases`.

**Body structure:**
- Who they are, in 1–2 sentences.
- `## Goals` — what they come to the product for, and what matters to them (speed, control, compliance…).
- `## Can and cannot` — the business rules on what they may do and why. The permission matrix is in the code: give the reasons and the exceptions, not the list.
- `## Pain points` — known frustrations, with their sources.

Features link their roles in `roles`. Keep it under 300 words.
