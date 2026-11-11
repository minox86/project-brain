---
name: concept
area: functional
folder: functional/concepts
max_words: 250
fields:
  kind: {kind: enum, values: [entity, state, event, document, measure, other]}
  term_en: {kind: string}
  term_it: {kind: string}
required: [term_en]
---
# Concept

A domain term of the product's ubiquitous language: an entity, a state, an event, a document, a measure that people and code refer to by name. Concepts make the glossary (`functional/concepts/README.md`), the shared vocabulary of the team, the code and the agents.

**Create** a page when a term is used with a specific meaning in this product, when people use different words for the same thing, or when the same word means different things.

**Do not create** a page for generic software terms (API, cache, user) unless the product gives them a specific meaning. User roles are `role` pages.

**Fields:** `kind` what sort of term it is; `term_en` the canonical English term (usually the title), the one to use in code; `term_<lang>` the term in each other glossary language. Put synonyms in `aliases`.

**Body structure:**
- Definition in 1–3 sentences, in business terms.
- `## Lifecycle` — for entities and documents with states: the states and what moves it from one to the next, as the business sees them (the code's enum is not enough).
- `## Examples` — one or two concrete examples.
- `## Not to be confused with` — near terms, linked.

Keep it under 250 words.
