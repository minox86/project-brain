---
name: integration
area: technical
folder: technical/integrations
max_words: 400
fields:
  kind: {kind: enum, values: [api, events, file, sso, sdk, other]}
  provider: {kind: string}
  used_by: {kind: list, of: link, to: module}
  docs: {kind: string}
required: []
---
# Integration

An external system the product talks to: a public authority (e.g. SDI), a payment provider, an identity provider, a partner's API, a SaaS. The knowledge here is almost never in the code: how the other side really behaves.

**Create** a page for every external system the product depends on at runtime, or that people discuss by name.

**Do not create** a page for libraries with no remote counterpart, nor for internal services (those are modules).

**Fields:** `provider` is who runs it; `used_by` the modules that call it; `docs` the link to the provider's documentation (never copy it).

**Body structure:**
- `## Purpose` — what the product uses it for, in 1–2 lines.
- `## Real behaviour` — what differs from the provider's docs or is not in them: quirks, rate limits, timeouts, retries that are safe or not, data formats it rejects, maintenance windows.
- `## Contract` — what the product relies on (versions, guarantees, SLA) and what breaks if it changes.
- `## Operations` — sandbox and production, how to get access (process, not credentials), the support channel, what to do when it is down.

**Never** write credentials, tokens or customer data. Keep it under 400 words.
