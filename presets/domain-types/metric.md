---
name: metric
area: functional
folder: functional/metrics
max_words: 300
fields:
  unit: {kind: string}
  source: {kind: string}
  applies_to: {kind: list, of: link}
  status: {kind: enum, values: [active, retired], default: active}
required: []
---
# Metric

A product or business measure the team steers by, with its exact definition.

**Create** a page when a measure is used to take decisions and people could compute it in different ways.

**Do not create** a page for technical monitoring (latency, error rates: they live in the observability tools) nor for one-off analyses.

**Fields:** `unit` (count, %, €, days); `source` where the official value is computed (dashboard, query); `applies_to` the features it measures.

**Body structure:**
- The definition in 1–2 sentences, precise enough to compute.
- `## Calculation` — what is counted, what is excluded, the time window, the events or fields it reads.
- `## Why it matters` — the decision it informs, the target if any.

Keep it under 300 words.
