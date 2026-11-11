# Verification spikes

Run these on real accounts before rolling project-brain out to the team. Each one checks an assumption the design (`docs/specs/2026-11-11-git-interaction-redesign.md` §10) depends on, and names the fallback if it fails.

## S1 — Cowork reads `brain/` on the default branch through the GitHub connector

**Steps**
1. In Cowork, as a non-developer account with read access to the monorepo, connect the GitHub connector and install the `pb` plugin.
2. Ask `/pb:ask what modules does the product have?` and `/pb:context <a feature title>`, without selecting any branch.

**Expected:** Claude reads `brain/index.md`, `brain/glossary.md`, `brain/context/<feature>.md` and linked pages from the default branch, and answers with `[[Page]]` citations. Check whether a large monorepo hits the connector's size limits.

**If it fails:** publish a read-only Confluence mirror of `brain/` from a GitHub Action (deferred phase), and point read mode at it through the Atlassian connector.

## S2 — the cloud routine pushes to `docs/brain` and opens the PR to the default branch

**Steps**
1. Create the routine with `/pb:routine-setup` (target branch `docs/brain`), commit its configuration and merge its PR, then "Run now".
2. Let a run ingest a page on a watched point (e.g. a decision).

**Expected:** `pb routine finish` pushes to `docs/brain` (not a `claude/…` branch): `docs/brain` is unprotected, so no bypass is needed. The PR "Brain updates" from `docs/brain` to the default branch is found or opened through `gh api`, its description lists the watched change, and the area reviewers are requested on it.

**If it fails:** if the push goes to a `claude/…` branch, say explicitly in the prompt that it may push to `docs/brain`; if `gh api` is not available, the run reports it in `problems` and the PR is opened by hand.

## S3 — Microsoft 365 connector reads channel messages incrementally

**Steps:** in a Claude Code session with the connector, call `teams_list_channel_messages` on a busy channel; page through results; check replies are included and that filtering by date is possible.

**Expected:** messages and thread replies after a given time can be listed completely.

**If it fails:** use `chat_message_search` with date filters; reduce the number of channels; run the routine more often to keep pages short.

## S4 — Confluence CQL by `lastmodified` through the Atlassian connector in routines

**Steps:** in a routine "Run now", call `searchConfluenceUsingCql` with `space = "<KEY>" AND type = page AND lastmodified > "<date>"`.

**Expected:** new and modified pages are returned with their version.

**If it fails:** list the configured page tree (`getConfluencePageDescendants`) and compare versions with `brain/.pb/state/confluence.json`.

## S5 — Python in Cowork

**Steps:** in Cowork, with the plugin installed, ask Claude to run `python3 --version`.

**Expected:** not required. Read mode only reads files. Note the result: if Python is available, read mode could use `pb context` directly.

## S6′ — the routine restarts `docs/brain` when the default branch changed workflow files

**Steps**
1. Let the routine open "Brain updates", then merge it with the repository's usual merge method (squash included) or with `/pb:merge`.
2. Merge a code PR that changes a file under `.github/workflows/`.
3. Run the routine ("Run now", or `/pb:routine-run`).

**Expected:** `docs/brain` holds nothing the default branch lacks, so the run restarts it from the default branch (a non-fast-forward push) and the push is accepted although the new history carries workflow changes. The next "Brain updates" shows only the new pages.

**If it fails:** the routine leaves `docs/brain` as it is and reports it as behind, in the digest and in the PR description; the maintainer realigns it with `/pb:merge`.

## S7 — a workflow requests reviewers with the default token

**Steps:** in a working branch, change a page on a watched point (e.g. accept a decision) and open a PR; watch the `review` job of `pb-validate`.

**Expected:** the job summary lists the watched points, and the area reviewers in `brain/schema/review.md` (users and teams) are requested on the PR with the workflow's default `GITHUB_TOKEN`.

**If it fails:** the `review` job only writes the summary and a PR comment; the reviewers are asked by hand.
