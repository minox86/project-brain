# Shared conventions of the `pb` skills

Every `pb` skill reads this file before acting. Skills that write to the brain also read `writing.md`, next to it. BASE is the skill's base directory, shown when the skill loads; the plugin root is `BASE/../..`.

## Toolkit

    PB = python3 "BASE/../../scripts/pb.py"

(`${CLAUDE_PLUGIN_ROOT}/scripts/pb.py` is the same file.)

- Every command prints one JSON object. Exit `0` ok; `1` findings described in the JSON; `2` usage or environment error (read `error`).
- Run from anywhere inside the monorepo; the brain is found by walking up to `brain/schema/VERSION`. Otherwise pass `--brain <dir>` or set `PB_BRAIN`.
- Never do by hand what the toolkit does: validation, name resolution, context packs, stats, lint, sync cursors, commits.

| Command | Use |
|---|---|
| `PB version` | `brain` is the brain path, or `null` outside a brain |
| `PB validate [paths…] [--base REF]` | Check pages against the schema, secrets, budgets and the review policy; noise warnings on pages created or updated since `REF` (default `HEAD`). Warnings never fail |
| `PB review [--base REF] [--confidence PATH=LEVEL…]` | Apply `brain/schema/review.md` to the pages changed since `REF`: which go straight to the branch, which are held for a PR, why, and the reviewers per area |
| `PB resolve "<name>" [--type T]` | Candidate pages for a name (`title`, `alias`, `partial`, `fuzzy`) |
| `PB context (--jira KEY \| --feature T \| --paths P…) [--max-words N]` | Context pack: pages + markdown (`--jira` matches epics and features; `--feature` takes any feature or epic title) |
| `PB prs --since ISO [--repo owner/name]` | Merged PRs since the cursor that touch a module (via `gh`): only those reach you, with modules, matched files, diff size and description; plus the new `cursor` |
| `PB stats` | Pages and words per type/area, over-budget pages, largest pages |
| `PB lint` | Structural findings (validate errors, budgets, duplicates, orphans, stale, archivable, dead module paths, superseded references) |
| `PB state get <source> [key]` / `PB state set <source> <key> <json>` | Sync cursors (`teams`, `confluence`, `github`, `jira`, `meetings`) |
| `PB state suppress <source> "<claim>"` | Claim corrected by `/pb:fix` that sync must not re-ingest |
| `PB correction --page P --wrong W --right R --evidence E` | Append to `brain/.pb/corrections.md` |
| `PB commit -m MSG [--allow-default] [--include PATH…]` | Commit `brain/` changes (generated files excluded), plus any `--include` paths, on the current branch |
| `PB routine start --branch B [--worktree DIR]` / `PB routine finish --branch B -m MSG [--confidence PATH=LEVEL…]` / `PB routine discard` / `PB routine cleanup --worktree DIR` | Routine runs: checkout target branch (or, for manual local runs, a detached worktree that leaves the user's checkout alone); commit, rebase, push; pages the review policy holds go to a `pb/review/<timestamp>` branch with a PR and reviewers; drop the run's brain changes except digests; remove the worktree |
| `PB scan [--repo DIR]` | Facts about the monorepo for bootstrap |
| `PB scaffold --product NAME [--repo DIR]` | Create `brain/`, CI workflows, CLAUDE.md pointer, vendored toolkit |
| `PB generate` | CI only: index, glossary, context packs, backlinks, digest retention |
| `PB toolkit-sync` | Refresh `brain/.pb/toolkit` after a plugin upgrade |

## Modes

Run `PB version` first.

- **Repo mode** — `brain` is a path: all skills available. You are in the monorepo (Claude Code).
- **Read mode** — `brain` is `null` or Python is unavailable, but a GitHub connector or tool can read the monorepo: only `/pb:ask`, `/pb:context` and `/pb:brief`. Read files from the default branch: `brain/index.md` first, then `brain/glossary.md`, `brain/context/<feature or active epic>.md`, and the pages they link. Never try to write.
- **Neither** — the brain is not reachable. Guide the user as **Connectors** below says for the GitHub connector (Cowork), or tell them to open the monorepo in Claude Code.

In read mode, write skills (`put`, `meeting`, `capture`, `fix`, `sync`, `lint`, `schema`, `init`, `routine-setup`, `routine-run`) do not run. Reply: "The brain is read-only here. Knowledge reaches it through the Teams channels and Confluence spaces the nightly routine reads; a developer can also add it with `/pb:put` or fix it with `/pb:fix`."

## Connectors

Many commands need a connector or a CLI. Check **before** starting the work, never halfway through: list what this run needs, see which tools are present, and resolve what is missing with the user first.

| Need | Connector or tool | Tools that prove it is there | Used by |
|---|---|---|---|
| Teams channels, meetings and their transcripts | **Microsoft 365** connector | `teams_list_channel_messages`, `outlook_calendar_search`, `read_resource` | `sync`, `meeting`, `routine-setup`, `routine-run --local` |
| Confluence pages, Jira issues and epics | **Atlassian** connector | `getConfluencePage`, `searchJiraIssuesUsingJql` | `put`, `sync`, `routine-setup`, `routine-run --local`, `init` (seeding), `context` (parent epic) |
| PRs and issues of the monorepo | **GitHub CLI** `gh`, logged in (Claude Code) | `gh auth status` succeeds | `put`, `sync`, `routine-setup` |
| Reading the brain from Cowork | **GitHub** connector with read access to the monorepo | a GitHub file-read tool | `ask`, `context` in read mode |
| Figma frames | **Figma** connector (optional) | Figma tools | `put` |
| Creating and starting routines | Claude Code `schedule` skill or remote-trigger tool | the tool is listed | `routine-setup`, `routine-run` |

When something is missing:
1. **Say what and why** in one line: "To read the Confluence page I need the Atlassian connector, which isn't connected."
2. **Connector present but not signed in** (only an `authenticate` tool is listed for it): start the sign-in with that tool and give the user the link it returns. Continue once they confirm.
3. **Connector absent**: give the steps for where the user is.
   - **Cowork or claude.ai**: **Customize → Connectors** (Settings → Connectors on claude.ai), find Atlassian / Microsoft 365 / GitHub / Figma, **Connect**, sign in with the work account. If it is not in the list or is locked, an organization Owner must enable it first: say so.
   - **Claude Code**: connectors added on claude.ai are available to Claude Code when signed in with the same account. After connecting, run `/mcp` to check its status and sign in, then retry; a new session may be needed.
   - **GitHub CLI**: suggest `! gh auth login` (the `!` runs it in this session), then `gh auth status`.
   - **GitHub connector in Cowork**: grant access to the monorepo (an organization-owned repo may need approval from a GitHub org owner).
4. **Offer a way forward now**, so the user is not blocked: paste the content, export the page to a file, or run the command in Claude Code instead of Cowork. Then wait for their choice.
5. **Never invent content** for a source you could not read.

The routine is not interactive: there, a missing connector skips that source, and the digest under "Problems" says which connector the routine's owner must connect and where (the steps above).

## Page format

- File name = `title` + `.md`, in the type's `folder`. Titles are unique across the brain and cannot contain `\ / : * ? " < > | # ^ [ ]`.
- Wikilinks always point to the canonical title: `[[Invoice]]`, or `[[Invoice|invoices]]` to display other text. In frontmatter quote them: `provided_by: "[[Billing]]"`, `affects: ["[[A]]", "[[B]]"]`.
- Implicit fields for every type: `type`, `title`, `aliases`, `summary` (one line, shown in the index), `created`, `updated`, `sources`.
- Dates are ISO `YYYY-MM-DD`; convert relative expressions against the date of the source.
- Quote frontmatter strings containing `, ` `: ` ` #` or starting with a symbol.
- External references: `jira:<KEY>`, `confluence:<SPACE>/<pageId>`, `teams:<team>/<channel>/<messageId>`, `teams:meeting/<id>`, `gh:pr/<n>`, `gh:issue/<n>`, `figma:<fileKey>/<nodeId>`, `url:<url>`, `raw:<path without .md>`.
- Relevant claims cite their source inline `^[jira:FIN-412]`; the same references go in `sources`.
- Never write a field you cannot infer with reasonable confidence: omit it.

## Reading economy

- **Don't re-read** what this session already holds: pages returned by `PB context`, pages you just wrote, the index after a search found the page.
- Read the smallest thing that answers: a context pack before single pages, `PB resolve` before the index, one page before its neighbours.
- Batch independent tool calls in one turn.
