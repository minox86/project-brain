---
name: module
area: technical
folder: technical/modules
max_words: 400
fields:
  paths: {kind: list, of: string}
  owner_team: {kind: string}
required: [paths]
---
# Module

A unit of the monorepo with its own responsibility: an app, a service, a library, a package.

**Only what the code does not say.** Before each line ask: would an agent reading the code under `paths` find it in a few minutes? If so, leave it out. Structure, dependencies, public functions, configuration, how to build or run it: the code and its manifests say it. What stays: why the module exists and where its boundary is, rules the code relies on but does not enforce, lessons paid for in incidents, the direction the team wants to take.

**Fields:** `paths` lists the monorepo paths the module owns (`apps/billing/**`, `packages/ui/`). It is not knowledge but the key that maps changed files to brain context: keep it accurate. `owner_team` only when CODEOWNERS does not say it.

**Create** a page for every deployable or reusable unit people refer to by name.

**Do not create** a page for an internal folder of a module; describe it inside the module page if it matters.

**Body structure** (omit a section with nothing non-derivable to say):
- `## Responsibility` — what it owns, in 1–3 lines, and above all what it deliberately does **not** do and where that lives instead.
- `## Invariants` — rules that must hold and that the code does not enforce by itself (ordering, uniqueness across services, "never call X before Y"), each with its reason.
- `## Pitfalls` — non-obvious behaviour that has bitten people, each with its source (incident, PR, thread).
- `## Direction` — known debt and where the team wants to take the module, linking the decisions.

Dependencies and contracts are not listed: the code and the `contract` pages say them. Keep it under 400 words.
