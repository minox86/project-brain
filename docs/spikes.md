# Verification spikes

Run these on real accounts before rolling project-brain out to the team. Each one checks an assumption the design (spec §8) depends on, and names the fallback if it fails.

## S1 — Cowork reads `brain/` through the GitHub connector

**Steps**
1. In Cowork, as a non-developer account with read access to the monorepo, connect the GitHub connector and install the `pb` plugin.
2. Ask `/pb:ask what modules does the product have?` and `/pb:context <a feature title>`.

**Expected:** Claude reads `brain/index.md`, `brain/glossary.md`, `brain/context/<feature>.md` and linked pages, and answers with `[[Page]]` citations. Check that the connector can read the `docs/brain` branch (the freshest brain) and not only the default branch, which gets the brain only when the PR from `docs/brain` is merged; and whether a large monorepo hits size limits.

**If it fails:** publish a read-only Confluence mirror of `brain/` from a GitHub Action (deferred phase), and point read mode at it through the Atlassian connector.

## S2 — the cloud routine pushes to `docs/brain`

**Steps**
1. Create the routine with `/pb:routine-setup` (target branch `docs/brain`), merge the review PR with its configuration, then "Run now".
2. Let a run ingest a page on a watched point (e.g. a decision).

**Expected:** `pb routine finish` pushes to `docs/brain` (not a `claude/…` branch): `docs/brain` is unprotected, so no bypass is needed. Held pages go to a `pb/review/<timestamp>` PR towards `docs/brain` opened through `gh api` (with reviewers), and the PR from `docs/brain` to the default branch is found or opened.

**If it fails:** if the push goes to a `claude/…` branch, say explicitly in the prompt that it may push to `docs/brain`; if `gh api` is not available, the run reports the review branch in `review.problems` and the PRs are opened by hand.

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

## S6 — the brain PR and the merge back into `docs/brain`

**Steps**
1. Save a page with `/pb:put` and check the PR "Brain updates" from `docs/brain` to the default branch: `pb-validate` (`validate`, `brain-only`) runs and passes.
2. Merge it with the repository's usual merge method (squash included), then save another page.
3. Merge a code PR that changes a file under `.github/workflows/`, then merge the brain PR again.

**Expected:** after each merge, `pb-brain-branch` merges the default branch back into `docs/brain`, and the next brain PR shows only the new pages. With a workflow file changed on the default branch, the merge back needs the `PB_BRAIN_TOKEN` secret (a token with the `workflow` scope): without it the job fails with a message that says so.

**If it fails:** run `pb-brain-branch` by hand (workflow_dispatch) after setting `PB_BRAIN_TOKEN`; as a last resort, merge the default branch into `docs/brain` locally and push.
