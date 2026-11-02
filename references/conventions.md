# Shared conventions of the `pb` skills

Every `pb` skill reads this file before acting. Skills that write to the brain also read `writing.md`, next to it. BASE is the skill's base directory, shown when the skill loads; the plugin root is `BASE/../..`.

## Toolkit

    PB = python3 "BASE/../../scripts/pb.py"

(`${CLAUDE_PLUGIN_ROOT}/scripts/pb.py` is the same file.)

- Every command prints one JSON object. Exit `0` ok; `1` findings described in the JSON; `2` usage or environment error (read `error`).
- Run from anywhere inside the monorepo. In repo mode every command that reads or writes pages takes `--brain <brain>` (the managed copy returned by `PB workspace sync`, see **Modes**); otherwise the brain is found by walking up to `brain/schema/VERSION`, or from `PB_BRAIN`.
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
| `PB workspace sync` | Prepare the managed copy of the brain (`docs/brain`) and bring it up to date: `brain` is the path to pass as `--brain`; also reports `leftovers` (pages written but not saved), `rebase_in_progress`, `unpushed` saves |
| `PB save -m MSG [PATH…] [--force-review]` / `PB save --continue` | Save the pages written in the managed copy: only the `PATH`s given (the pages this work created, changed or deleted; without paths, every unsaved file), so another session's drafts are never swept in. Validates, commits, regenerates index and context packs, pushes to `docs/brain`; pages on watched points, and every change under `schema/` or `.pb/toolkit/`, go to a `pb/review/<timestamp>` PR instead; keeps the PR from `docs/brain` to the default branch open. `--continue` after resolving a conflict |
| `PB commit -m MSG [--allow-default] [--include PATH…]` | Init only: commit `brain/` changes (generated files excluded), plus any `--include` paths, on the current branch |
| `PB routine start --branch B [--worktree DIR]` / `PB routine finish --branch B -m MSG [--confidence PATH=LEVEL…]` / `PB routine discard` / `PB routine cleanup --worktree DIR` | Routine runs: checkout target branch (or, for manual local runs, a detached worktree that leaves the user's checkout alone); commit, rebase, push; pages the review policy holds go to a `pb/review/<timestamp>` branch with a PR and reviewers; drop the run's brain changes except digests; remove the worktree |
| `PB scan [--repo DIR]` | Facts about the monorepo for bootstrap |
| `PB scaffold --product NAME [--repo DIR]` / `PB scaffold --upgrade [--repo DIR]` | Create `brain/`, CI workflows, CLAUDE.md pointer, plugin settings, vendored toolkit / move an older brain to `docs/brain` (current workflows, plugin settings, toolkit, `AGENTS.md` writing rule) |
| `PB generate` | Index, glossary, context packs, backlinks, digest retention. `PB save` and `PB routine finish` run it: never by hand |
| `PB toolkit-sync` | Refresh `brain/.pb/toolkit` (scripts, plus the sync/put/meeting skills and these references the cloud routine follows, since routines load no plugins) after a plugin upgrade |

## Modes

Run `PB workspace sync` first (the brain is not in the user's checkout, so `PB version` alone cannot find it):

- **Repo mode** — it answers with a `brain`: you are in a clone of the monorepo, with Python and git (Claude Code), and all skills are available. Use its `brain` as `--brain` for every `PB` command and as the folder where you read and write pages. The brain always lives on the branch `docs/brain`; the managed copy sits inside the clone's git folder, so the user's checkout, branch and uncommitted code are never touched and nobody needs to know git. Results of `sync`:
  - `code: no-brain` → no brain yet: `/pb:init` creates it.
  - `code: busy` → another session is saving: retry in a moment.
  - `leftovers` → pages written earlier and never saved: see **Before writing** in `writing.md`.
  - not a clone, or `git`/`python3` missing → `/pb:setup` prepares the computer.
- **Read mode** — Python or a clone are not available, but a GitHub connector or tool can read the monorepo: only `/pb:ask` and `/pb:context`. Read files from the branch `docs/brain`: `brain/index.md` first, then `brain/glossary.md`, `brain/context/<feature or active epic>.md`, and the pages they link. Never try to write.
- **Neither** — the brain is not reachable. Guide the user as **Connectors** below says for the GitHub connector (Cowork), or suggest `/pb:setup` in Claude Code.

In read mode, write skills (`put`, `meeting`, `capture`, `fix`, `sync`, `lint`, `schema`, `init`, `routine-setup`, `routine-run`) do not run. Reply: "The brain is read-only here. In Claude Code (`/pb:setup` prepares it once) anyone can write it; the nightly routine also brings in the Teams channels and Confluence spaces it reads."

The brain on `docs/brain` is always the latest. It reaches the code branches through one PR from `docs/brain` to the default branch that pb keeps open and the team merges when it wants: the `brain/` folder in a code checkout can be a few days behind, the managed copy never is.

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
