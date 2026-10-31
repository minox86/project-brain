# project-brain (`pb`)

A Claude plugin, for Claude Code and Claude Cowork, that keeps a **product brain** inside the product monorepo. `brain/` is a typed, linked Markdown wiki of functional concepts and features, epics in progress, technical modules and interfaces, decisions and open questions. It is fed by the team's Teams channels, Confluence spaces, Jira epics, merged PRs and developer sessions, and it is written for AI agents as much as for people.

Design: [`docs/specs/2026-10-31-project-brain-design.md`](docs/specs/2026-10-31-project-brain-design.md) · verification spikes: [`docs/spikes.md`](docs/spikes.md)

## How it works

- **Developers** (Claude Code, repo mode) read and write the brain. Their changes are committed on their current branch and travel with their PR.
- **Non-developers** (Cowork, read mode) read the brain through the GitHub connector with `/pb:ask` and `/pb:context`. Their knowledge reaches the brain through the Teams channels and Confluence spaces the nightly routine ingests.
- A **nightly cloud routine**, owned by the Engineering Manager, ingests Teams threads (triaged), new or changed Confluence pages and merged PRs. It pushes directly, without a PR, to a branch chosen at setup.
- **CI** in the monorepo validates `brain/` on PRs, auto-merges brain-only PRs, and regenerates `index.md`, `glossary.md` and `context/` on the default branch.

## Requirements

- Claude Code or Claude Cowork
- Python 3.9+ and git (repo mode)
- Connectors: Atlassian (Confluence, Jira) and Microsoft 365 (Teams) for ingestion; GitHub for read mode in Cowork

## Install

- **Claude Code:** `/plugin marketplace add <org>/project-brain`, then `/plugin install pb@project-brain`
- **Cowork:** the org admin syncs this repository as a marketplace (Organization settings → Plugins & skills) and makes `pb` available or installed by default for the product team.

## Commands

| Command | Mode | Purpose |
|---|---|---|
| `/pb:init` | repo | Grill-style interview to tailor the schema, then scaffold `brain/` and bootstrap it from the code |
| `/pb:put <input>` | repo | Ingest text, files, Confluence, Jira, GitHub PRs/issues, Figma, web pages |
| `/pb:meeting [last\|today\|link]` | repo | Ingest a Teams meeting (no transcript stored) |
| `/pb:capture` | repo | Distil the current session into the brain |
| `/pb:fix <what is wrong>` | repo | Correct wrong information everywhere it appears, and log the correction |
| `/pb:sync [sources] [--check]` | repo | Incremental ingestion from Teams, Confluence, GitHub, Jira |
| `/pb:ask <question>` | repo + read | Answers with citations |
| `/pb:context <jira\|feature\|epic\|paths>` | repo + read | Context pack for an agent or a person |
| `/pb:lint [--fix]` | repo | Maintenance: budgets, duplicates, orphans, stale and dead items |
| `/pb:schema [action]` | repo | Evolve the schema |
| `/pb:routine-setup` | repo | Configure the nightly routine |

All commands also trigger from natural language.

## Toolkit

`scripts/pb.py` is a deterministic CLI that uses only the Python standard library. It covers validate, resolve, context, generate, stats, lint, state, commit, routine, scan, scaffold and toolkit-sync, and every command prints JSON. `pb scaffold` copies it into `brain/.pb/toolkit/` so the monorepo's CI can run it. Run `pb toolkit-sync` after upgrading the plugin.

## Development

    python3 -m unittest discover -s tests -v   # toolkit tests
    claude plugin validate . --strict          # manifest and skills
    claude --plugin-dir .                      # try the plugin locally
