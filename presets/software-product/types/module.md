---
name: module
area: technical
folder: technical/modules
max_words: 600
fields:
  paths: {kind: list, of: string}
  owner_team: {kind: string}
  interfaces: {kind: list, of: link, to: interface}
  depends_on: {kind: list, of: link, to: module}
required: [paths]
---
# Module

A unit of the monorepo with its own responsibility: an app, a service, a library, a package.

**Fields:** `paths` lists the monorepo paths the module owns (`apps/billing/**`, `packages/ui/`); it is how agents map changed files to brain context, so keep it accurate.

**Create** a page for every deployable or reusable unit people refer to by name.

**Do not create** a page for an internal folder of a module; describe it inside the module page if it matters.

**Body structure:**
- `## Responsibility` — what it owns and what it explicitly does not.
- `## Key behaviours` — non-obvious runtime behaviour, invariants, gotchas not evident from the code.
- `## Dependencies` — why it depends on what it depends on (the list is in `depends_on`).

Do not describe what the code already says plainly. Keep it under 600 words.
