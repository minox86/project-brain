# project-brain (`pb`)

A Claude plugin, for Claude Code and Claude Cowork, that keeps a **product brain** inside the product monorepo. `brain/` is a typed, linked Markdown wiki of functional concepts and features, epics in progress, technical modules and interfaces, decisions and open questions. It is fed by the team's Teams channels, Confluence spaces, Jira epics, merged PRs and developer sessions, and it is written for AI agents as much as for people.

Design: [`docs/specs/2026-10-31-project-brain-design.md`](docs/specs/2026-10-31-project-brain-design.md) · verification spikes: [`docs/spikes.md`](docs/spikes.md)

## Quick start

### 1. Install the plugin (once per person)

**Claude Code**

```
/plugin marketplace add <org>/project-brain
/plugin install pb@project-brain
```

**Cowork**: nothing to do. The org admin adds this repo as a marketplace (Organization settings → Plugins & skills) and enables `pb` for the team. Then connect **GitHub** (read access to the monorepo) in Cowork.

### 2. Create the brain (once per product, one developer)

Requirements: Python 3.9+ and git.

1. Open the monorepo in Claude Code and create a branch: `git switch -c pb/init`.
2. Run `/pb:init`. Claude scans the repo, then asks you a few rounds of questions to tailor the schema. Answer "yes" to accept a recommendation.
3. Confirm the final schema. Claude then:
   - creates `brain/`;
   - adds two GitHub workflows;
   - adds a pointer in `CLAUDE.md`;
   - proposes a first set of pages.
4. Open a PR and merge it.

In the monorepo's GitHub settings:
- **Actions → General → Workflow permissions**: "Read and write".
- **General → Allow auto-merge**: on. PRs that touch only `brain/` then merge on their own once validated.
- If `main` is protected, let GitHub Actions push to it, or the index and context packs won't refresh.

### 3. Set up the nightly routine (once, Engineering Manager)

1. Make sure the Microsoft 365 and Atlassian connectors are enabled in your Claude account.
2. In the monorepo, run `/pb:routine-setup` and choose:
   - the Teams channels and Confluence spaces to read;
   - the Jira projects whose epics to follow;
   - the branch the routine pushes to (`main`, or a branch like `brain/inbox` that you merge yourself).
3. Merge the configuration, then follow the printed steps: `/schedule`, paste the prompt, then **Run now**.
4. Check `brain/digests/<today>.md` on the target branch: it lists what was ingested and what was skipped.

### 4. Daily use

**Developers (Claude Code)**

| You want to… | Run |
|---|---|
| Get context before a ticket | `/pb:context FIN-412` (or a feature, an epic, or file paths) |
| Ask something | `/pb:ask why do invoices have a single approver?` |
| Save what you learned in this session | `/pb:capture` (at the end of a task) |
| Add a document, page or ticket | `/pb:put <file \| Confluence link \| jira:KEY \| text>` |
| Save a Teams meeting | `/pb:meeting last` |
| Correct something wrong | `/pb:fix <what is wrong and what is right>` |
| Tidy up | `/pb:lint --fix` |

Brain changes are committed on your current branch and go out with your PR. You can also just ask in plain words ("save this decision in the brain").

**PMs, designers, analysts, QA (Cowork)**

- Ask questions: `/pb:ask what is still open on multi-level approval?`
- Get a briefing: `/pb:context <feature, epic or Jira key>`

The brain is read-only from Cowork. To add knowledge, write it where you already do: your analyses on Confluence, your discussions in the Teams channel. Mention the Jira epic key and the routine files it under that epic.

### 5. Something is off?

- **"The brain is not reachable"** (Cowork): connect GitHub with read access to the monorepo.
- **Nothing was ingested overnight**: read the "Problems" section of the latest digest in `brain/digests/`.
- **Wrong information**: a developer runs `/pb:fix`. Anyone else reports it in the Teams channel and the routine picks it up.

## How it works

- **Developers** (Claude Code, repo mode) read and write the brain. Their changes are committed on their current branch and travel with their PR.
- **Non-developers** (Cowork, read mode) read the brain through the GitHub connector with `/pb:ask` and `/pb:context`. Their knowledge reaches the brain through the Teams channels and Confluence spaces the nightly routine ingests.
- A **nightly cloud routine**, owned by the Engineering Manager, ingests Teams threads (triaged), new or changed Confluence pages and merged PRs. It pushes directly, without a PR, to a branch chosen at setup.
- **CI** in the monorepo validates `brain/` on PRs, auto-merges brain-only PRs, and regenerates `index.md`, `glossary.md` and `context/` on the default branch.

## Requirements

- Claude Code or Claude Cowork
- Python 3.9+ and git (repo mode)
- Connectors: Atlassian (Confluence, Jira) and Microsoft 365 (Teams) for ingestion; GitHub for read mode in Cowork

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

## License

[MIT](LICENSE)
