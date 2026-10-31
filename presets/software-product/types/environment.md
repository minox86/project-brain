---
name: environment
area: technical
folder: technical/environments
max_words: 300
fields:
  kind: {kind: enum, values: [dev, staging, prod, other]}
  url: {kind: string}
required: []
---
# Environment

A runtime environment of the product: what runs there and how to work with it.

**Body structure:**
- `## Purpose` — who uses it and for what.
- `## Operational notes` — data refresh, feature flags, known limits, how to get access (process, not credentials).

**Never** write credentials, tokens, connection strings or personal data. Keep it under 300 words.
