---
name: sync
description: Incrementally ingests into the project brain what changed in the configured sources since the last run — Teams channel threads (triaged), new or modified Confluence pages, merged GitHub PRs touching known modules, Jira epics of the configured projects, transcripts of the configured recurring Teams meetings — using stored cursors, and writes a digest when run by the routine. Use when the user asks to sync or update the brain from Teams, Confluence, GitHub or Jira, to check what would be ingested, or when the nightly routine runs.
argument-hint: "[teams] [confluence] [github] [jira] [meetings] [--check] [--digest]"
---

# /pb:sync — incremental ingestion

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

## 0. Setup

- Sources: the ones named in the arguments; none named → `teams confluence github jira meetings`.
- `--check`: report what would be ingested, write nothing, move no cursor.
- `--digest`: write `brain/digests/YYYY-MM-DD.md` (always on when run by the routine).
- Read `brain/schema/sources.md`. A source with no configuration is skipped with a note ("run `/pb:routine-setup`").
- For each source read its state: `PB state get <source>`. `suppressed` lists claims corrected by `/pb:fix`: never re-ingest them.
- Connectors: interactive run → check those the selected sources need before starting and guide the user to connect what is missing (see **Connectors** in the conventions); they may also choose to skip that source. Routine run → skip the source and write under "Problems" which connector the routine's owner must connect.

## Readers: raw content stays out of this session

Teams threads, Confluence pages and meeting transcripts are the bulk of what a sync reads. You do not read them yourself: **readers** do, and return findings (`BASE/../../references/reader.md`). You then resolve, decide and write from the findings alone.

- **Subagents available** (the Agent tool): dispatch one reader per unit, all in one message so they run in parallel: one per Teams channel, one per Confluence space, one per meeting occurrence. Use the `sonnet` model unless this session already runs on it or on a smaller one. Each reader's prompt holds:
  - the instruction to follow `BASE/../../references/reader.md`, with its absolute path;
  - the unit: the tools to use, the ids, the cursor and, for Confluence, the stored `versions`;
  - `suppressed` from the source's state;
  - the active epics: title, aliases and `jira` key of each page in `brain/epics/` whose `status` is `active`.
- **No subagents**: act as the reader yourself, one unit at a time, following the same brief, and keep only the findings.

Readers never write. You keep the significance gate: findings marked `?` are yours to decide. `--check`: report the readers' verdicts and findings without writing.

## 1. Teams (Microsoft 365 connector)

For each configured channel (`teams:` entries):
1. Cursor: `PB state get teams <id>` → `{"cursor": "<ISO datetime>"}`; no cursor → last 7 days.
2. A reader reads the channel (`teams_list_channel_messages` after the cursor), groups threads, defers active ones and triages the rest.
3. Ingest the `knowledge` findings like `/pb:put` (significance gate → resolve → write), routing by epic (see **Epic routing** below). Cite `teams:<team>/<channel>/<root message id>`; never name people. `signal` items go to the digest; `ignore` items are counted.
4. New cursor: the reader's `CURSOR` (never past a deferred thread).

## 2. Confluence (Atlassian connector)

For each configured space (`confluence:` entries):
1. Cursor: `PB state get confluence <id>` → `{"cursor": "<YYYY-MM-DD HH:MM>", "versions": {"<pageId>": <version>}}`.
2. A reader searches with `searchConfluenceUsingCql`: `space = "<SPACE>" AND type = page AND lastmodified > "<cursor>"` (add `AND ancestor = <root_page>` when configured); no cursor → last 30 days. It skips pages whose version equals the stored one before fetching them.
3. Ingest the findings like `/pb:put`: analyses and requirements are summarised and linked (the page stays authoritative on requirement detail); decisions, concepts and behaviour go into typed pages citing `confluence:<SPACE>/<pageId>`. Route by epic (below).
4. Update `versions` and the cursor from the reader's `VERSIONS` and `CURSOR`.

## Epic routing (Teams and Confluence)

A thread or page that mentions a Jira epic key, or the title or an alias of an `epic` page, feeds that epic:
- delivery-specific content (scope agreements, constraints, risks, the takeaway of the discussion) → the epic page, `## Agreed scope`, `## Constraints and risks`, `## Discussion`;
- durable content (behaviour, concepts, decisions, open questions) → its own pages as usual, linked from the epic (`affects: ["[[<epic>]]"]` on decisions and open questions).

Unknown epic key in a `knowledge` thread or page: `getJiraIssue`. If it is an Epic of a configured `jira:` project, create its `epic` page; otherwise cite the key as plain text.

## 3. GitHub (merged pull requests)

1. Cursor: `PB state get github cursor` (ISO datetime); no cursor → 7 days ago.
2. `PB prs --since <cursor>`. The toolkit reads the merged PRs through `gh`, matches their files against `module.paths` and returns only the PRs that touch a module: number, title, url, modules, matched files, diff size and description (`body_truncated` when cut). PRs touching no module are listed in `skipped`: count them in the digest. `code: gh-missing` or `gh-failed`: see **Connectors** in the conventions (in the routine, record it under "Problems").
3. For each PR, keep from title and description only what passes the significance gate: technical decisions and their reasons, changed module responsibilities, new or changed interfaces, behaviour changes of features. Read more (`gh api repos/<repo>/pulls/<n>`, or the diff of `matched_files`) only when the description is truncated or too thin to tell. Cite `gh:pr/<n>`. `gh pr …` is unavailable in cloud routines: use `gh api` only.
4. New cursor: the `cursor` returned by `PB prs`.

## 4. Jira (epics)

For each configured project (`jira:` entries):
1. Cursor: `PB state get jira <id>` → `{"cursor": "<YYYY-MM-DD HH:MM>"}`; no cursor → last 30 days.
2. `searchJiraIssuesUsingJql` with `project = <KEY> AND issuetype = Epic AND updated > "<cursor>"`.
3. Epic with an `epic` page: align `status` (Jira done → `done`, won't do → `cancelled`) and the `## Goal` if the epic's description changed its meaning. An epic that just became done or cancelled is **closed** as its type prose says, in the same run: what is still true moves into feature, concept, module and decision pages; the body becomes `## Outcome`.
4. Epic without a page: create it only if it is discussed beyond its ticket (linked Confluence pages, remote links, comments with substance). Otherwise skip it: the significance gate applies.
5. Only when `jira` is named explicitly: also features with `jira:` keys (`key in (…) AND updated > "<cursor>"`). Update only their summary and links; raise an `open-question` when Jira contradicts the brain.
6. New cursor: the latest `updated` processed.

## 5. Meetings (recurring series, Microsoft 365 connector)

For each configured series (`meetings:` entries):
1. Cursor: `PB state get meetings <id>` → `{"cursor": "<ISO datetime>"}`: the end of the last occurrence processed. No cursor → last 7 days.
2. `outlook_calendar_search` with `query: "<subject>"`, `organizer: "<organizer>"`, `afterDateTime: <cursor>`, `beforeDateTime: now`, `order: oldest`. Keep occurrences that have **ended** and whose subject matches; skip cancelled ones. This list is small: read it yourself.
3. One reader per occurrence, oldest first: transcript (`meetingTranscriptUrl` from the event, verbatim, scoped to the occurrence with `start`/`end`) and meeting chat. A reader returning `deferred` (ended less than 24 hours ago, no transcript yet) stops this series for this run. `skipped` (no transcript after 24 hours) is recorded as "no transcript: transcription may be off for this series, or the routine's account was not invited".
4. Write the findings without asking for confirmation, with the rules of `/pb:meeting` step 3 (`BASE/../meeting/SKILL.md`). Cite `teams:meeting/<event id>`.
5. New cursor: the end time of the last occurrence fully processed (never past a deferred one).

## 6. Write, digest, cursors

1. Validate as in the closing flow (fix errors, condense over-budget pages).
2. With `--digest`, write `brain/digests/YYYY-MM-DD.md` (no frontmatter):

       # Digest YYYY-MM-DD
       ## Ingested
       - <source ref> → [[Page]] (created|updated): <one line>
       ## Signals
       - <source ref>: <one line>
       ## Skipped
       - <n> threads ignored; <source ref>: <reason>
       ## Deferred
       - <n> active threads
       ## Pending review
       - [[Page]]: <reasons from PB review>
       ## Problems
       - <missing connectors, errors, previous run failures>
       ## Brain size
       - <pages> pages, <words> words; over budget: <titles>

   Take the size from `PB stats`. For "Pending review": rate the confidence of every page you created or updated (see **Confidence and review** in the writing conventions), run `PB review --confidence <path>=<level>…` passing only pages below high, and list the pages it holds with their reasons. Keep the same `--confidence` arguments for `PB routine finish`.
3. Only after the pages are written and valid, move the cursors: `PB state set <source> <key> '<json>'`.
4. Interactive run: closing flow (`PB commit -m "pb(sync): <sources> <date>"`). Routine run: the routine prompt handles commit and push.
