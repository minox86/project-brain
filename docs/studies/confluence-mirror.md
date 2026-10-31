# Study — read-only Confluence mirror of the brain

Status: proposal, not implemented. Date: 2026-10-31.

## Goal

PMs, analysts and designers read the brain **in Confluence**, where they already work, without Cowork, the plugin or GitHub access. No new habits: they open a page tree in their usual space.

## What the current tools allow

Verified against the Atlassian connector available to the routine:

- `createConfluencePage` and `updateConfluencePage` accept `contentFormat: "markdown"` for basic formatting (headings, lists, tables, links). Brain pages can be sent almost as they are; no HTML converter is needed.
- Pages go under a `parentId` in a space (`spaceId` accepts the space key), and an update can carry a `versionMessage`.
- `getConfluencePage` returns the current version, so the routine can detect pages edited by hand.
- The connector has no tools to set labels or page restrictions. Edit restrictions on the mirror tree must be set once, by hand, by a space admin.

The routine already runs with the Atlassian connector and the Engineering Manager's account, so the mirror needs **no new credentials and no new infrastructure**.

## Options

| | A. Routine publishes through the connector | B. GitHub Action with the Confluence REST API | C. Rovo indexes the repo | D. Confluence macro that embeds GitHub files |
|---|---|---|---|---|
| New credentials | none | API token of a service account, stored as a repo secret | Rovo GitHub connector, set up by an Atlassian admin | Marketplace app, plus repo access for it |
| Process change | none | none | users search in Rovo instead of browsing pages | none |
| Freshness | each routine run | each merge | Rovo's indexing interval | live |
| Determinism | LLM issues the calls; content is rendered by the toolkit | fully deterministic | n/a | n/a |
| Build effort | toolkit renderer + skill step (~1–2 days) | renderer + Markdown→storage conversion + workflow (~3 days) | configuration only | configuration only |
| Main risk | Markdown fidelity; token cost scales with changed pages | owning a token and a converter | licence and availability; not browsable as pages | private repos, app approval, rendering of wikilinks |

**Recommendation: A.** It is the only option that works with what we already have and asks nothing of the users. B is the upgrade path if the mirror must refresh on every merge or the token cost becomes noticeable. C is worth asking the Atlassian admin about, because it costs nothing to build if Rovo is already licensed, but it does not give browsable pages.

## Proposed design (option A)

### What is mirrored

| Confluence page | Source | Notes |
|---|---|---|
| **Product Brain** (root) | `index.md` | Intro line, sections Functional / Technical / Epics / Decisions, links to the child pages |
| **Glossary** | `glossary.md` | Bilingual table |
| **Features / \<title\>** | `functional/features/*` | One page each |
| **Epics / \<title\>** | `epics/*`, active only | Closed epics are archived (below) |
| **Decisions / \<title\>** | `decisions/*`, not superseded | Superseded ones are archived |
| **Open questions** | `open-questions/*`, open only | One summary page with a table, not one page each |

Modules, interfaces and environments are not mirrored: they matter to developers, who read the repo. A setting can turn them on.

### Rendering (toolkit, deterministic)

A new command, `pb mirror plan [--ref origin/<default>]`:
- reads the brain **from the default branch**, so the mirror never shows unmerged routine output;
- renders each mirrored page to Confluence-ready Markdown:
  - frontmatter → a small properties table (status, Jira key, area, updated);
  - `[[Title]]` → a link to the mirrored page when its Confluence id is known, otherwise the title in bold;
  - `^[source]` citations → links (`jira:KEY` → Jira URL, `confluence:SPACE/id` → page URL, `teams:` → plain reference);
  - footer: "Generated from `brain/<path>` at `<sha>`. Edits here are overwritten: discuss in Teams or write an analysis page instead.";
- compares a hash of each rendered body with `.pb/state/mirror.json` (`{title: {page_id, hash, version}}`) and outputs `create`, `update`, `archive` and `unchanged` lists. Bodies go to `.pb/cache/mirror/` so the LLM passes them on verbatim and never rewrites them.

`pb mirror record --title T --page-id ID --version N --hash H` updates the state after each call.

### Publishing (routine step, after sync)

1. `PB mirror plan`; nothing to do → stop.
2. **create**: `createConfluencePage` under the right section parent, `contentFormat: markdown`, body from the cache file. Then `PB mirror record`.
3. **update**: `getConfluencePage` first. If its version is higher than the recorded one, someone edited the mirror by hand: treat their change as a **contribution**. Ingest it with the `/pb:put` rules (significance gate; an `open-question` if it contradicts the brain), list it in the digest, then overwrite. Otherwise `updateConfluencePage` with `versionMessage: "pb mirror <sha7>"`, then record.
4. **archive**: move the page under an **Archive** parent (`updateConfluencePage` with a new `parentId`) instead of deleting it, so links keep working.
5. Digest: "Mirror: N created, M updated, K archived, J hand edits ingested".

Hand edits thus become a third zero-change contribution channel, next to Teams and Confluence analyses.

### Configuration

`brain/schema/sources.md` gains `mirror: {space: <KEY>, parent_page: <id>, include: [feature, epic, decision, open-question, glossary]}`, set by a new step in `/pb:routine-setup`. That step creates the root and section pages, and asks the user to have a space admin restrict editing of the tree to the routine owner (optional: hand edits are ingested anyway).

### Cost and limits

- Only changed pages are sent: a typical night touches a handful. The initial publication of a large brain is the expensive run; it can be capped per run (e.g. 50 pages) and continue the next night.
- Brain pages are capped at 200–600 words, so each call is small.
- Confluence titles must be unique within a space. If a title is taken, prefix it with the product name and record the mapping.

## Spikes before building

1. **Fidelity:** create a page in markdown with a table, nested bullets and links. Check the rendering, then update it and check that the page id and history are kept.
2. **Move:** archive a page by changing `parentId`.
3. **Edit detection:** edit a page by hand, then read the version number through `getConfluencePage`.
4. **Permissions:** confirm the routine owner can create pages in the target space, and that restricted pages stay editable by that account.
5. **Rovo (option C):** ask the Atlassian admin whether the Rovo GitHub connector is available. If it is, compare it with A before building.

## Effort

- Toolkit `mirror plan` / `mirror record` with tests: about one day.
- Routine step, `/pb:routine-setup` step, digest line and README: about half a day.
- Spikes: half a day with access to a test space.
