---
name: edition
area: functional
folder: functional/editions
max_words: 350
fields:
  kind: {kind: enum, values: [edition, plan, add-on], default: edition}
  status: {kind: enum, values: [on-sale, planned, retired], default: on-sale}
  applies_to: {kind: list, of: link}
  roles: {kind: list, of: link, to: role}
required: []
---
# Edition

A commercial package of the product: an edition, a subscription plan, a licence tier or an add-on, and what it unlocks.

**Create** a page for every package customers can buy that changes which features they see or the limits they have.

**Do not create** a page for a price change or a promotion: prices stay in the commercial systems.

**Fields:** `kind` edition, plan or add-on; `applies_to` the features it includes; `roles` who typically buys or uses it.

**Body structure:**
- Who it is for, in 1–2 lines.
- `## Includes` — features and limits (users, documents, companies…), linked.
- `## Differences` — what changes compared with the nearest packages, and upgrade paths.

Where entitlements are enforced is in the code: write what is sold and why, not how it is checked. Keep it under 350 words.
