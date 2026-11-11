---
name: contract
area: technical
folder: technical/contracts
max_words: 400
fields:
  kind: {kind: enum, values: [api, event, data, library, ui]}
  provided_by: {kind: link, to: module}
  external_consumers: {kind: list, of: string}
  spec_path: {kind: string}
required: []
---
# Contract

A technical agreement between modules or with the outside world: an API (REST, GraphQL, gRPC: the text says which), an event, exchanged files, data formats and shared schemas (`data`), a library API, a UI contract.

**Only what the spec and the code do not say.** Paths, payloads, types and the list of internal callers are in the spec and the code: never copy them.

**Create** a page when a contract is consumed by more than one module or by an external party, and its semantics are not obvious from its spec.

**Fields:** `spec_path` points to the machine-readable spec in the repo (OpenAPI, AsyncAPI, proto, JSON Schema) when it exists. `external_consumers` names consumers outside the monorepo (partner, mobile app, another product): internal consumers are found in the code.

**Body structure:**
- `## Purpose` — what the contract is for, in 1–2 lines.
- `## Semantics` — meaning, ordering, idempotency, error handling, versioning and compatibility promises: what the spec does not say.
- `## Consumers` — only promises made to specific consumers, or why a consumer uses it in an unusual way.

Keep it under 400 words.
