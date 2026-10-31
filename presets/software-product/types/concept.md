---
name: concept
area: functional
folder: functional/concepts
max_words: 200
fields:
  term_en: {kind: string}
  term_it: {kind: string}
required: [term_en]
---
# Concept

A domain term of the product's ubiquitous language: an entity, a state, a role, a rule that people and code refer to by name. Concepts feed the bilingual glossary.

**Create** a page when a term is used with a specific meaning in this product, when people use different words for the same thing, or when the same word means different things.

**Do not create** a page for generic software terms (API, cache, user) unless the product gives them a specific meaning.

**Fields:** `term_en` is the canonical English term (usually the title); `term_it` the Italian term used by the team. Put synonyms in `aliases`.

**Body structure:**
- Definition in 1–3 sentences.
- `## Examples` — one or two concrete examples.
- `## Not to be confused with` — near terms, linked.

Keep it under 200 words.
