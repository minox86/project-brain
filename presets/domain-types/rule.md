---
name: rule
area: functional
folder: functional/rules
max_words: 350
fields:
  basis: {kind: enum, values: [law, contract, policy, convention]}
  status: {kind: enum, values: [active, planned, retired], default: active}
  applies_to: {kind: list, of: link}
  regulation: {kind: link, to: regulation}
  valid_from: {kind: date}
required: [basis]
---
# Rule

A business rule the product must apply in more than one place: a calculation, a validation, a constraint, an eligibility condition. One rule, one page, linked from every feature it shapes, so it is never restated differently in several features.

**Create** a page when a rule is applied by more than one feature or module, or when its reason or source must be known to change it safely.

**Do not create** a page for a rule that lives entirely inside one feature (write it in that feature's `## Expected behaviour`), nor for technical validation (formats, lengths) with no business meaning.

**Fields:** `basis` why the rule exists (`law` and `contract` cannot be changed by the team; `policy` and `convention` can); `regulation` the norm it comes from, when there is a `regulation` type; `applies_to` the features, concepts and modules it governs; `valid_from` when it took effect.

**Body structure:**
- The rule in 1–3 sentences, precise enough to test.
- `## Details` — formulas, thresholds, rounding, exceptions, with examples.
- `## Source` — where it comes from (norm, contract clause, decision), linked.

A rule replaced by a new one: set `status: retired`, create the new page and link it. Keep it under 350 words.
