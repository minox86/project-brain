# Verification spikes

Run these on real accounts before rolling project-brain out to the team. Each one checks an assumption the design (spec §8) depends on, and names the fallback if it fails.

## S1 — Cowork reads `brain/` through the GitHub connector

**Steps**
1. In Cowork, as a non-developer account with read access to the monorepo, connect the GitHub connector and install the `pb` plugin.
2. Ask `/pb:ask what modules does the product have?` and `/pb:context <a feature title>`.

**Expected:** Claude reads `brain/index.md`, `brain/glossary.md`, `brain/context/<feature>.md` and linked pages from the default branch, and answers with `[[Page]]` citations. Check how fresh the content is after a merge, and whether a large monorepo hits size limits.

**If it fails:** publish a read-only Confluence mirror of `brain/` from a GitHub Action (deferred phase), and point read mode at it through the Atlassian connector.

## S2 — the cloud routine pushes directly to the target branch

**Steps**
1. Create the routine with `/pb:routine-setup` on a test branch (`brain/inbox`), then once targeting the default branch with the bypass in place.
2. "Run now".

**Expected:** `pb routine finish` pushes to the configured branch (not a `claude/…` branch), and on the default branch the push is accepted with the owner's bypass. `pb-generate` runs after the push to the default branch.

**If it fails:** use a long-lived target branch merged by hand; or tell the routine explicitly in its prompt that it may push to `{{branch}}`.

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
