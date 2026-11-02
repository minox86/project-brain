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

A runtime environment of the product: what it is for and how to work with it.

**Only what the infrastructure code does not say.** Sizing, services deployed and configuration are in the IaC and the pipelines: do not repeat them.

**Body structure:**
- `## Purpose` — who uses it and for what.
- `## Operational notes` — data refresh, feature flags policy, known limits, who may deploy and when, how to get access (process, not credentials).

**Never** write credentials, tokens, connection strings or personal data. Keep it under 300 words.
