---
name: interface
area: technical
folder: technical/interfaces
max_words: 400
fields:
  kind: {kind: enum, values: [rest, event, grpc, lib, ui-contract]}
  provided_by: {kind: link, to: module}
  consumed_by: {kind: list, of: link, to: module}
  spec_path: {kind: string}
required: []
---
# Interface

A contract between modules or with the outside world: a REST API, an event, a gRPC service, a library API, a UI contract.

**Create** a page when a contract is consumed by more than one module or by an external party, or when its semantics are not obvious from its spec.

**Fields:** `spec_path` points to the machine-readable spec in the repo (OpenAPI, AsyncAPI, proto) when it exists; do not copy the spec.

**Body structure:**
- `## Purpose` — what the contract is for.
- `## Semantics` — meaning, ordering, idempotency, error handling, versioning rules: what the spec does not say.
- `## Consumers` — how and why consumers use it, when it matters.

Keep it under 400 words.
