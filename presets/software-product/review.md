---
direct_min_confidence: high
noise_to_review: true
reviewers:
  technical: []
  functional: []
  ux: []
watch:
  - {type: decision, why: "decisions constrain future work"}
  - {type: contract, why: "contracts between modules or with the outside world"}
  - {type: integration, change: [create, delete], why: "external systems the product depends on"}
  - {type: feature, fields: [status], why: "feature status changes"}
  - {type: concept, change: create, why: "new glossary terms"}
  - {type: module, fields: [paths], why: "module boundaries"}
  - {type: "*", change: delete, why: "deleted pages"}
---
# Review policy

Decides which brain changes a human must look at. Nothing is held back: watched changes are named on the PR that carries them, and the area reviewers are asked there. Written by `/pb:init`, changed with `/pb:schema`. `PB review` applies it; `PB validate` checks it.

Where it applies:
- **Pages written in a working branch** (`PB save`): the save names the watched points touched; on the PR, CI lists them and requests the reviewers. The user confirmed what they save, so confidence and noise never flag a page here. Changes to `.pb/schema/` (this file included) and to the toolkit are always watched.
- **Routine runs**: the same, plus the routine's own confidence ratings and, with `noise_to_review`, its noise warnings, all in the description of the Brain updates PR.

## Fields

- `direct_min_confidence`: `low`, `medium` or `high`. A page the writer rated below this level is flagged for review. `high`: only what the model is sure of goes unflagged. `low`: confidence never flags anything.
- `noise_to_review`: `true` flags pages that still carry a noise warning from `PB validate` (`possible-duplicate`, `new-orphan`, `missing-source`, `log-heading`, `ephemeral`, `verbatim`).
- `reviewers`: GitHub users (`login`) or teams (`org/team-slug`) per area: `technical` (modules, contracts, integrations, environments, technical decisions), `functional` (features, processes, concepts, roles, functional decisions), `ux` (design decisions). A page with no area of its own (open questions, decisions without `area`) asks every area.
- `watch`: the points of the schema where any change needs a review. Each rule matches when all its keys match:
  - `type`: a type name, a list, or `"*"`;
  - `change`: `create`, `update`, `delete`, or a list (default: any);
  - `fields`: frontmatter fields; the rule matches only when one of them changes;
  - `area`: `technical`, `functional`, `ux`, or a list;
  - `why`: shown in the PR next to the page.

## Confidence

The writer rates every page it creates or updates:
- **high**: stated explicitly and settled in the source (an accepted decision, a written requirement, merged code);
- **medium**: inferred from the source, or from one voice in a discussion that did not visibly conclude;
- **low**: an interpretation, an ambiguous name resolution, a contradiction with the brain, a type chosen with doubt.

A page that links a new flagged page is flagged with it, so the reviewer sees both.
