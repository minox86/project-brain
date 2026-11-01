---
direct_min_confidence: high
noise_to_review: true
reviewers:
  technical: []
  functional: []
  ux: []
watch:
  - {type: decision, why: "decisions constrain future work"}
  - {type: interface, why: "contracts between modules"}
  - {type: feature, fields: [status], why: "feature status changes"}
  - {type: concept, change: create, why: "new glossary terms"}
  - {type: module, fields: [paths], why: "module boundaries"}
  - {type: "*", change: delete, why: "deleted pages"}
---
# Review policy

Decides which brain changes reach the branch directly and which wait in a pull request for a human. Written by `/pb:init`, changed with `/pb:schema`. `PB review` applies it; `PB validate` checks it.

Where it applies:
- **Routine runs**: held changes go to a `pb/review/<timestamp>` branch with a PR towards the routine branch, reviewers requested; everything else is pushed as before.
- **Pull requests from developers**: CI requests the reviewers and does not auto-merge a brain-only PR when it touches a watched point.

## Fields

- `direct_min_confidence`: `low`, `medium` or `high`. A page the writer rated below this level is held for review. `high`: only what the model is sure of goes straight in. `low`: confidence never holds anything.
- `noise_to_review`: `true` holds pages that still carry a noise warning from `PB validate` (`possible-duplicate`, `new-orphan`, `missing-source`, `log-heading`, `ephemeral`, `verbatim`).
- `reviewers`: GitHub users (`login`) or teams (`org/team-slug`) per area: `technical` (modules, interfaces, environments, technical decisions), `functional` (features, concepts, functional decisions), `ux` (design decisions). A page with no area of its own (epics, open questions, decisions without `area`) asks every area.
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

A page that links a new page held for review is held with it, so the branch never has broken links.
