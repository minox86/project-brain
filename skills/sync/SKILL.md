---
name: sync
description: Incrementally ingests into the project brain what changed in the configured sources since the last run — Teams channel threads (triaged), new or modified Confluence pages, merged GitHub PRs touching known modules, Jira epics and issues of the configured projects, transcripts of the configured recurring Teams meetings — using stored cursors, and writes a digest when run by the routine. Use when the user asks to sync or update the brain from Teams, Confluence, GitHub or Jira, to check what would be ingested, or when the nightly routine runs.
argument-hint: "[teams] [confluence] [github] [jira] [meetings] [--check] [--digest]"
---

# /pb:sync — incremental ingestion

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

## 0. Setup

- **Where it runs.** Always a routine run on `docs/brain` (see **Modes** in the conventions), never in the user's checkout: the cursors live there. Started by the routine prompt or by `/pb:routine-run`: the run is already started, use its brain. Typed by the user: say in one line that the result goes to `docs/brain` and the Brain updates PR, not to the current branch; then `PB routine start --branch docs/brain --worktree <tmp dir outside the repo>`; from then on run every `PB` command and read and write every `brain/…` path against its `brain`, as **Modes** says.
- Sources: the ones named in the arguments; none named → `teams confluence github jira meetings`.
- `--check`: report what would be ingested, write nothing, move no cursor; then `PB routine cleanup` (step 6).
- `--digest`: write `brain/.pb/digests/YYYY-MM-DD.md` (always on when run by the routine).
- Read `brain/.pb/schema/sources.md`. A source with no configuration is skipped with a note ("run `/pb:routine-setup`").
- For each source read its state: `PB state get <source>`. `suppressed` lists claims corrected by `/pb:fix`: never re-ingest them.
- Connectors: interactive run → check those the selected sources need before starting and guide the user to connect what is missing (see **Connectors** in the conventions); they may also choose to skip that source. Scheduled routine → skip the source and write under "Problems" which connector the routine's owner must connect.

## Readers: raw content stays out of this session

Teams threads, Confluence pages and meeting transcripts are the bulk of what a sync reads. You do not read them yourself: **readers** do, and return findings (`BASE/../../references/reader.md`). You then resolve, decide and write from the findings alone.

- **Subagents available** (the Agent tool): dispatch one reader per unit, all in one message so they run in parallel: one per Teams channel, one per Confluence space, one per meeting occurrence. Use the `sonnet` model unless this session already runs on it or on a smaller one. Each reader's prompt holds:
  - the instruction to follow `BASE/../../references/reader.md`, with its absolute path;
  - the unit: the tools to use, the ids, the cursor and, for Confluence, the stored `versions`;
  - `suppressed` from the source's state.
- **No subagents**: act as the reader yourself, one unit at a time, following the same brief, and keep only the findings.

Readers never write. You keep the significance gate: findings marked `?` are yours to decide. `--check`: report the readers' verdicts and findings without writing.

## 1. Teams (Microsoft 365 connector)

For each configured channel (`teams:` entries):
1. Cursor: `PB state get teams <id>` → `{"cursor": "<ISO datetime>"}`; no cursor → last 7 days.
2. A reader reads the channel (`teams_list_channel_messages` after the cursor), groups threads, defers active ones and triages the rest.
3. Ingest the `knowledge` findings like `/pb:put` (significance gate → resolve → write), routing by Jira key (see **Jira key routing** below). Cite `teams:<team>/<channel>/<root message id>`; never name people. `signal` items go to the digest; `ignore` items are counted.
4. New cursor: the reader's `CURSOR` (never past a deferred thread).

## 2. Confluence (Atlassian connector)

For each configured space (`confluence:` entries):
1. Cursor: `PB state get confluence <id>` → `{"cursor": "<YYYY-MM-DD HH:MM>", "versions": {"<pageId>": <version>}}`.
2. A reader searches with `searchConfluenceUsingCql`: `space = "<SPACE>" AND type = page AND lastmodified > "<cursor>"` (add `AND ancestor = <root_page>` when configured); no cursor → last 30 days. It skips pages whose version equals the stored one before fetching them.
3. Ingest the findings like `/pb:put`: analyses and requirements are summarised and linked (the page stays authoritative on requirement detail); decisions, concepts and behaviour go into typed pages citing `confluence:<SPACE>/<pageId>`. Route by Jira key (below).
4. Update `versions` and the cursor from the reader's `VERSIONS` and `CURSOR`.

## Jira key routing (Teams and Confluence)

A thread or page that mentions a Jira key listed in a feature's `jira` feeds that feature and the pages it links. An unknown key: `getJiraIssue` only to find which feature it belongs to (its epic or parent listed in a feature's `jira`); none → ingest the content like any other. What is specific to delivering the work stays in Jira (**Work in Jira** in `writing.md`).

## 3. GitHub (merged pull requests)

1. Cursor: `PB state get github cursor` (ISO datetime); no cursor → 7 days ago.
2. `PB prs --since <cursor>`. The toolkit reads the merged PRs through `gh`, matches their files against `module.paths` and returns only the PRs that touch a module: number, title, url, modules, matched files, diff size and description (`body_truncated` when cut). PRs touching no module are listed in `skipped`: count them in the digest. `code: gh-missing` or `gh-failed`: see **Connectors** in the conventions (in the routine, record it under "Problems").
3. For each PR, keep from title and description only what passes the significance gate: technical decisions and their reasons, changed module responsibilities, new or changed contracts, behaviour changes of features. Read more (`gh api repos/<repo>/pulls/<n>`, or the diff of `matched_files`) only when the description is truncated or too thin to tell. Cite `gh:pr/<n>`. `gh pr …` is unavailable in cloud routines: use `gh api` only.
4. New cursor: the `cursor` returned by `PB prs`.

## 4. Jira

For each configured project (`jira:` entries):
1. Cursor: `PB state get jira <id>` → `{"cursor": "<YYYY-MM-DD HH:MM>"}`; no cursor → last 30 days.
2. `searchJiraIssuesUsingJql` with `project = <KEY> AND updated > "<cursor>"`: the epics and issues changed since the cursor, read as documents.
3. Keep what passes the significance gate (requirement clarifications, decisions, open questions, the feature's expected behaviour), as **Work in Jira** in `writing.md` says: add the key to the `jira` of the feature the work delivers or changes, and set the feature's `status` to `released` when Jira says the work is released. No page is created per epic; a contradiction with the brain becomes an `open-question`.
4. New cursor: the latest `updated` processed.

## 5. Meetings (recurring series, Microsoft 365 connector)

For each configured series (`meetings:` entries):
1. Cursor: `PB state get meetings <id>` → `{"cursor": "<ISO datetime>"}`: the end of the last occurrence processed. No cursor → last 7 days.
2. `outlook_calendar_search` with `query: "<subject>"`, `organizer: "<organizer>"`, `afterDateTime: <cursor>`, `beforeDateTime: now`, `order: oldest`. Keep occurrences that have **ended** and whose subject matches; skip cancelled ones. This list is small: read it yourself.
3. One reader per occurrence, oldest first: transcript (`meetingTranscriptUrl` from the event, verbatim, scoped to the occurrence with `start`/`end`) and meeting chat. A reader returning `deferred` (ended less than 24 hours ago, no transcript yet) stops this series for this run. `skipped` (no transcript after 24 hours) is recorded as "no transcript: transcription may be off for this series, or the routine's account was not invited".
4. Write the findings without asking for confirmation, with the rules of `/pb:meeting` step 3 (`BASE/../meeting/SKILL.md`). Cite `teams:meeting/<event id>`.
5. New cursor: the end time of the last occurrence fully processed (never past a deferred one).

## 6. Write, digest, cursors

1. `PB validate <every page this run created or changed>`: fix errors and retry at most twice; condense over-budget pages. Still failing: `PB --brain <brain> routine discard`, write the failure under "Problems" in the digest, move no cursor.
2. With `--digest`, write `brain/.pb/digests/YYYY-MM-DD.md` (no frontmatter):

       # Digest YYYY-MM-DD
       ## Ingested
       - <source ref> → <page title> (created|updated): <one line>
       ## Signals
       - <source ref>: <one line>
       ## Skipped
       - <n> threads ignored; <source ref>: <reason>
       ## Deferred
       - <n> active threads
       ## Watched
       - <page title>: <reasons from PB review>
       ## Problems
       - <missing connectors, errors, previous run failures>
       ## Brain size
       - <pages> pages, <words> words; over budget: <titles>

   Take the size from `PB stats`. For "Watched": rate the confidence of every page you created or updated (see **Confidence and review** in the writing conventions), run `PB review --confidence <path>=<level>…` passing only pages below high, and list the pages it flags with their reasons. Keep the same `--confidence` arguments for `PB routine finish`.
3. Only after the pages are written and valid, move the cursors: `PB state set <source> <key> '<json>'`.
4. Started by the routine prompt or by `/pb:routine-run`: stop here; their own steps finish the run (in the scheduled routine a `rejected` commit is reported in the run's final summary, with the hook's output: the digest is not committed). Typed by the user:
   - `PB --brain <brain> routine finish --branch docs/brain --skill sync -m "<sources> <YYYY-MM-DD>"`, with `--confidence` for pages below high (pages the user confirmed count as high). It commits, pushes `docs/brain` and keeps the Brain updates PR open, with the watched changes and their reviewers. With `rejected`, nothing was pushed: handle it as the closing flow of `writing.md` says (the same command with `--raw -m "<message>"`, every other argument unchanged).
   - Always end with `PB routine cleanup --worktree <tmp dir>`, also after `--check` or a stop.
   - Report: pages ingested (as Markdown links to their repo path), the PR (`pr`), the `watched` points and their reviewers, and `problems` one line each. `behind` > 0: "`docs/brain` is behind <default>: run `/pb:merge` to bring these changes to <default>". `"conflict": true`: nothing was pushed and no cursor moved; running `/pb:sync` again picks the same content up.
