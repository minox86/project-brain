---
name: regulation
area: functional
folder: functional/regulations
max_words: 400
fields:
  authority: {kind: string}
  reference: {kind: string}
  status: {kind: enum, values: [in-force, upcoming, repealed], default: in-force}
  effective: {kind: date}
  applies_to: {kind: list, of: link}
  url: {kind: string}
required: [authority]
---
# Regulation

An external norm the product must comply with: a law, a decree, an authority's circular or technical specification, a standard. The norm stays authoritative: the page says what it imposes on this product and how the product complies.

**Create** a page for every norm that constrains how features behave, or whose changes the team must track.

**Do not create** a page for norms that do not touch the product's behaviour, nor copy the norm's text.

**Fields:** `authority` who issues it (e.g. "Agenzia delle Entrate"); `reference` its official identifier; `effective` when it applies; `url` the official text; `applies_to` the features, rules and integrations it constrains.

**Body structure:**
- What it is, in 1–2 lines.
- `## What it imposes` — the obligations that concern this product, as bullets, each precise enough to check.
- `## How we comply` — which features, rules and integrations implement it; gaps go in open questions.
- `## Deadlines and changes` — effective dates, transitional periods, announced changes.

Keep it under 400 words.
