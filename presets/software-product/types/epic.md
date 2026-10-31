---
name: epic
area: cross
folder: epics
max_words: 500
fields:
  jira: {kind: string}
  status: {kind: enum, values: [active, done, cancelled], default: active}
  features: {kind: list, of: link, to: feature}
  modules: {kind: list, of: link, to: module}
required: [jira]
---
# Epic

A Jira epic in progress: the change the team is delivering and everything discussed about it in Teams, Confluence and meetings that the people building it must take into account.

**Feature or epic?** A `feature` describes how the product behaves, now or once released, and stays true after the work ends. An `epic` holds only what is specific to delivering one change: agreed scope, constraints, risks, points still being discussed, pointers to the discussion. If a statement will still be true after the epic closes, write it on the feature, concept, module or decision page and link it from here. One epic can touch several features; a feature can be changed by several epics; a technical epic may touch no feature at all.

**Create** a page when a Jira epic is discussed beyond its ticket (Teams threads, Confluence analyses, meetings). Title it with the epic name; put the key in `jira`.

**Do not create** a page for an epic that only exists in Jira with no discussion around it, nor for stories or tasks: they stay in Jira.

**Body structure:**
- `## Goal` — the change and why, in 1–3 lines.
- `## Agreed scope` — in / out, as bullets, as agreed so far; link requirement documents instead of copying them.
- `## Constraints and risks` — what implementation must respect, each with its source.
- `## Discussion` — one line per relevant thread, analysis or meeting: the takeaway and its reference. Not a chronological log: drop lines once their content is settled elsewhere.

Decisions and open questions get their own pages with `affects` pointing to the epic.

**Close** it when the Jira epic is done: move what is still true into feature, concept, module and decision pages, then replace the body with `## Outcome` (1–3 lines) and set `status: done` (or `cancelled`, with one line on why). Closed epics leave the index after `archive_after_days`.

Keep it under 500 words.
