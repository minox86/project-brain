---
name: sync
description: Incrementally ingests into the project brain what changed in the configured sources since the last run — Teams channel threads (triaged), new or modified Confluence pages, merged GitHub PRs touching known modules, Jira epics of the configured projects — using stored cursors, and writes a digest when run by the routine. Use when the user asks to sync or update the brain from Teams, Confluence, GitHub or Jira, to check what would be ingested, or when the nightly routine runs.
argument-hint: "[teams] [confluence] [github] [jira] [--check] [--digest]"
---

# /pb:sync — incremental ingestion

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Repo mode only.

## 0. Setup

- Sources: the ones named in the arguments; none named → `teams confluence github jira`.
- `--check`: report what would be ingested, write nothing, move no cursor.
- `--digest`: write `brain/digests/YYYY-MM-DD.md` (always on when run by the routine).
- Read `brain/schema/sources.md`. A source with no configuration is skipped with a note ("run `/pb:routine-setup`").
- For each source read its state: `PB state get <source>`. `suppressed` lists claims corrected by `/pb:fix`: never re-ingest them.
- Connectors: interactive run → check those the selected sources need before starting and guide the user to connect what is missing (see **Connectors** in the conventions); they may also choose to skip that source. Routine run → skip the source and write under "Problems" which connector the routine's owner must connect.

## 1. Teams (Microsoft 365 connector)

For each configured channel (`teams:` entries):
1. Cursor: `PB state get teams <id>` → `{"cursor": "<ISO datetime>"}`; no cursor → last 7 days.
2. `teams_list_channel_messages` for messages and replies after the cursor; page through all results.
3. Group by **thread** (root message + replies). Never ingest a message out of its thread.
4. **Defer** threads whose last reply is less than 24 hours old: they are still being discussed. The cursor must not move past the root of a deferred thread.
5. **Triage** each complete thread:
   - `knowledge` — a decision, a requirement clarification, a domain explanation, an incident learning, an open question → ingest;
   - `signal` — relevant but not durable (progress, coordination) → digest only;
   - `ignore` — noise → digest count only.
6. Ingest `knowledge` threads like `/pb:put` (analyse → significance gate → resolve → write), routing by epic (see **Epic routing** below). Cite `teams:<team>/<channel>/<root message id>`; never store message text verbatim, never name people.
7. New cursor: the latest message time fully processed (before any deferred thread).

## 2. Confluence (Atlassian connector)

For each configured space (`confluence:` entries):
1. Cursor: `PB state get confluence <id>` → `{"cursor": "<YYYY-MM-DD HH:MM>", "versions": {"<pageId>": <version>}}`.
2. `searchConfluenceUsingCql` with `space = "<SPACE>" AND type = page AND lastmodified > "<cursor>"` (add `AND ancestor = <root_page>` when configured); no cursor → last 30 days.
3. For each page: skip it if its version equals the stored one; otherwise `getConfluencePage` and ingest like `/pb:put` — analyses and requirements are summarised and linked (the page stays authoritative on requirement detail); decisions, concepts and behaviour go into typed pages citing `confluence:<SPACE>/<pageId>`. Route by epic (below).
4. Update `versions` and the cursor.

## Epic routing (Teams and Confluence)

A thread or page that mentions a Jira epic key, or the title or an alias of an `epic` page, feeds that epic:
- delivery-specific content (scope agreements, constraints, risks, the takeaway of the discussion) → the epic page, `## Agreed scope`, `## Constraints and risks`, `## Discussion`;
- durable content (behaviour, concepts, decisions, open questions) → its own pages as usual, linked from the epic (`affects: ["[[<epic>]]"]` on decisions and open questions).

Unknown epic key in a `knowledge` thread or page: `getJiraIssue`. If it is an Epic of a configured `jira:` project, create its `epic` page; otherwise cite the key as plain text.

## 3. GitHub (merged pull requests)

1. Repo from `github.repo` in `sources.md`. Cursor: `PB state get github cursor` (ISO datetime); no cursor → last 7 days.
2. `gh api "repos/<repo>/pulls?state=closed&sort=updated&direction=desc&per_page=100"`; keep PRs with `merged_at` after the cursor. (`gh pr …` is unavailable in cloud routines: use `gh api` only.)
3. For each PR: `gh api repos/<repo>/pulls/<n>/files --paginate` → file paths → `PB context --paths <files…>`. No module matched → skip (count it in the digest).
4. From title, description and diff summary keep only what passes the significance gate: technical decisions and their reasons, changed module responsibilities, new or changed interfaces, behaviour changes of features. Cite `gh:pr/<n>`.
5. New cursor: the latest `merged_at` processed.

## 4. Jira (epics)

For each configured project (`jira:` entries):
1. Cursor: `PB state get jira <id>` → `{"cursor": "<YYYY-MM-DD HH:MM>"}`; no cursor → last 30 days.
2. `searchJiraIssuesUsingJql` with `project = <KEY> AND issuetype = Epic AND updated > "<cursor>"`.
3. Epic with an `epic` page: align `status` (Jira done → `done`, won't do → `cancelled`) and the `## Goal` if the epic's description changed its meaning. An epic that just became done or cancelled is **closed** as its type prose says, in the same run: what is still true moves into feature, concept, module and decision pages; the body becomes `## Outcome`.
4. Epic without a page: create it only if it is discussed beyond its ticket (linked Confluence pages, remote links, comments with substance). Otherwise skip it: the significance gate applies.
5. Only when `jira` is named explicitly: also features with `jira:` keys (`key in (…) AND updated > "<cursor>"`). Update only their summary and links; raise an `open-question` when Jira contradicts the brain.
6. New cursor: the latest `updated` processed.

## 5. Write, digest, cursors

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
       ## Problems
       - <missing connectors, errors, previous run failures>
       ## Brain size
       - <pages> pages, <words> words; over budget: <titles>

   Take the size from `PB stats`.
3. Only after the pages are written and valid, move the cursors: `PB state set <source> <key> '<json>'`.
4. Interactive run: closing flow (`PB commit -m "pb(sync): <sources> <date>"`). Routine run: the routine prompt handles commit and push.
