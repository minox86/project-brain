# Shared conventions of the `pb` skills

Every `pb` skill reads this file before acting. Skills that write to the brain also read `writing.md`, next to it. BASE is the skill's base directory, shown when the skill loads; the plugin root is `BASE/../..`.

## Toolkit

    PB = python3 <absolute path of BASE/../../scripts/pb.py>

Resolve the path once (no `..`, no quotes unless it contains spaces), so permission rules like `Bash(python3 */scripts/pb.py *)` match. `${CLAUDE_PLUGIN_ROOT}/scripts/pb.py` is the same file.

- Every command prints one JSON object. Exit `0` ok; `1` findings described in the JSON; `2` usage or environment error (read `error`).
- Run from anywhere inside the monorepo: the brain is `brain/` of the current checkout. `--brain <dir>` (or `PB_BRAIN`) picks another brain, as routine runs in a worktree do; it goes before the command: `PB --brain <dir> resolve "<name>"`.
- Never do by hand what the toolkit does: validation, name resolution, link paths, context packs, generated files, stats, lint, sync cursors.

| Command | Use |
|---|---|
| `PB version` | `brain` is the brain path, or `null` outside a brain |
| `PB validate [paths…] [--base REF]` | Check pages against the schema, secrets, budgets and the review policy; noise warnings on pages created or updated since `REF` (default `HEAD`). Warnings never fail |
| `PB review [--base REF] [--confidence PATH=LEVEL…]` | Apply `brain/.pb/schema/review.md` to the pages changed since `REF`: which touch a watched point (or are rated too low, or carry noise), why, and the reviewers per area |
| `PB resolve "<name>" [--type T]` | Candidate pages for a name (`title`, `alias`, `partial`, `fuzzy`) |
| `PB context (--jira KEY \| --feature T \| --paths P…) [--max-words N]` | Context pack: pages + markdown with links valid from the repo root (`--jira` matches the features whose `jira` lists the key; `--feature` takes any feature title) |
| `PB prs --since ISO [--repo owner/name]` | Merged PRs since the cursor that touch a module (via `gh`): only those reach you, with modules, matched files, diff size and description; plus the new `cursor` |
| `PB stats` | Pages and words per type/area, over-budget pages, largest pages |
| `PB lint` | Structural findings (validate errors, budgets, duplicates, orphans, stale, archivable, dead module paths, superseded references) |
| `PB state get <source> [key]` / `PB state set <source> <key> <json>` | Sync cursors (`teams`, `confluence`, `github`, `jira`, `meetings`) |
| `PB state suppress <source> "<claim>"` | Claim corrected by `/pb:fix` that sync must not re-ingest |
| `PB correction --page P --wrong W --right R --evidence E` | Append to `brain/.pb/corrections.md` |
| `PB save [PATH…]` | Close a write in the working tree: normalise the links and headings of the pages among the `PATH`s given (the files this work created, changed or deleted; without paths, every changed brain file), check them, regenerate the generated files, report `watched` points and `reviewers`. Never commits or pushes. Returns `saved`, `errors`, `warnings` (anchors dropped), `normalised`, `files` (every changed brain file, the pages whose links it repaired included), `watched`, `reviewers`, `markdown`, `branch`, `on_default` |
| `PB generate` | The index `brain/README.md`, the `README.md` of every type folder (the glossary in `functional/concepts/`, the feature catalogue in `functional/features/`), context packs in `brain/.pb/context/`, backlinks. Safe by hand at any time; it is what resolves a conflict on generated files |
| `PB links [PATH…] [--check]` | Normalise page bodies (default: every page): `[[Title]]` becomes a Markdown link relative to the page, a link to a moved page is repaired, the `# <title>` heading is added or corrected. Frontmatter untouched. `PB save`, `PB routine finish` and `PB merge finish` run it on their pages (on every page when one was deleted, renamed or moved). Returns `changed`; `--check` changes nothing and exits 1 when a page would change (CI) |
| `PB commit -m SUMMARY [--skill S] [--raw] [--allow-default] [--include PATH…]` | Commit `brain/` changes (pages and generated files), plus any `--include` paths, on the current branch, with the message `commit_format` (`brain/.pb/schema/brain.md`) makes of `SUMMARY` and `S` (default `brain`); `--raw`: `-m` is the whole message. Only when the user asks, and in `/pb:init`. A commit the repo's hooks refuse returns `rejected` (`message`, `output`; `null` on success), exit 1, the changes left in place |
| `PB message -m SUMMARY [--skill S]` | The commit `message`, `pr_title_brain`, `pr_title_init`, `commit_format` and `commit_rules`; commits nothing |
| `PB routine start --branch B [--worktree DIR]` | Check out `B` (created or restarted from the default branch when needed), or with `--worktree` a temporary worktree (`worktree`, `brain`). Also `created`, `restarted`, `behind` |
| `PB routine finish --branch B -m SUMMARY [--skill S] [--raw] [--confidence PATH=LEVEL…]` | Normalise the run's pages, retention, regenerate, commit (`S` default `routine`), push `B`, keep the brain PR (`pr_title_brain`) open with reviewers. Never merges. Returns `committed`, `pushed`, `conflict`, `pr`, `watched`, `reviewers`, `behind`, `retention`, `problems`, `rejected` (a refused commit: nothing pushed, exit 1) |
| `PB routine discard` / `PB routine cleanup --worktree DIR` | Drop the run's brain changes except digests / remove the run's worktree |
| `PB retention [--today D]` | Flag old closed pages `archived`, delete old digests. `PB routine finish` runs it: never by hand |
| `PB merge start --worktree DIR` / `PB merge finish --worktree DIR -m SUMMARY [--raw]` / `PB merge land [--wait S]` | `/pb:merge` only: bring the default branch into `docs/brain`, push it, merge the "Brain updates" PR |
| `PB scan [--repo DIR]` | Facts about the monorepo for bootstrap, including the documentation inventory (`docs`, `docs_words`) and where the repo states its commit rules (`commit_rules`: `commitlint`, `hooks`, `pr_checks`, `recent_subjects`) |
| `PB scaffold --product NAME [--repo DIR]` / `PB scaffold --upgrade [--repo DIR]` | Create `brain/`, the CI workflow, CLAUDE.md pointer, plugin settings, vendored toolkit / bring an older brain up to date (workflow, plugin settings, toolkit, `AGENTS.md` writing rule) |
| `PB toolkit-sync` | Refresh `brain/.pb/toolkit` (scripts, plus the sync/put/meeting skills and these references the cloud routine follows, since routines load no plugins) after a plugin upgrade |

## Modes

Run `PB version` first:

- **Repo mode** — it answers with a `brain`: you are in a clone of the monorepo, with Python and git (Claude Code), and all skills are available. The brain is `brain/` in the working tree of this checkout, on whatever branch the developer is on: you read the brain as of that branch and write pages there, as ordinary changes of it. pb never commits, pushes, rebases or switches branch here: the developer commits the pages with the code and they reach the default branch with the code PR, where CI checks them and asks the area reviewers. With `brain: null`:
  - `git cat-file -e origin/<default>:brain/.pb/schema/VERSION` succeeds → this branch was cut before the brain arrived: say to bring the default branch into it; never do it yourself.
  - no brain on the default branch either → `/pb:init` creates it.
  - not a clone, or `git`/`python3` missing → `/pb:setup` prepares the computer.
  - a command answers `code: old-format`: the brain has the format of an earlier pb version; relay the message (remove `brain/`, create it again with `/pb:init`), never convert it.
- **Routine run** — the scheduled routine (`templates/routine/prompt.md`), `/pb:sync` and `/pb:routine-run --local`: always on the branch `docs/brain`, never in the user's checkout. In the cloud the routine checks it out (`PB routine start --branch docs/brain`); in Claude Code, `PB routine start --branch docs/brain --worktree <tmp dir outside the repo>` gives a temporary worktree: run every `PB` command as `PB --brain <brain from the result> …`; every `brain/…` path in the skills and references means `<brain>/…`, for reading and writing; always end with `PB routine cleanup --worktree <tmp dir>`. No `PB save`: `PB routine finish` commits and pushes `docs/brain` and keeps one PR, "Brain updates", to the default branch; nothing is ever merged by the run. Sync cursors change only here; suppressions from `/pb:fix` may also come from a working branch, and `/pb:merge` keeps both sides' suppressions. The scheduled routine never asks anything: what needs a human gets confidence `low`, so the PR flags it for the reviewers.
- **Read mode** — Python or a clone are not available, but a GitHub connector or tool can read the monorepo: only `/pb:ask` and `/pb:context`. Read `brain/` on the default branch (no branch to select): `brain/README.md` first, then the `README.md` of the folders it lists (the glossary `brain/functional/concepts/README.md`, the catalogue `brain/functional/features/README.md`), `brain/.pb/context/<feature>.md`, and the pages they link (links are relative to the file that holds them). Never try to write.
- **Neither** — the brain is not reachable. Guide the user as **Connectors** below says for the GitHub connector (Cowork), or suggest `/pb:setup` in Claude Code.

In read mode, write skills (`put`, `meeting`, `capture`, `fix`, `questions`, `sync`, `lint`, `schema`, `init`, `routine-setup`, `routine-run`, `merge`) do not run. Reply: "The brain is read-only here. To add knowledge, write it on Confluence or in the team's Teams channel (mention the Jira key): the nightly routine brings it in."

The default branch holds the brain everyone reads. A working branch adds its own pages until its PR is merged; what the routine writes waits on `docs/brain` in "Brain updates" until `/pb:merge` brings it to the default branch.

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
- Bodies start with `# <title>` and link pages with Markdown links relative to the page; write `[[Invoice]]` or `[[Invoice|invoices]]` and `PB save` turns them into those links (`writing.md`, **Links**). Frontmatter link fields hold plain titles: `provided_by: Billing`, `affects: [A, B]`.
- In chat, cite a page as a Markdown link to its repo path: `[Invoice](brain/functional/concepts/Invoice.md)`.
- Implicit fields for every type: `type`, `title`, `aliases`, `summary` (one line, shown in its folder's `README.md`), `created`, `updated`, `sources`.
- Dates are ISO `YYYY-MM-DD`; convert relative expressions against the date of the source.
- Quote frontmatter strings containing `, ` `: ` ` #` or starting with a symbol.
- External references: `jira:<KEY>`, `confluence:<SPACE>/<pageId>`, `teams:<team>/<channel>/<messageId>`, `teams:meeting/<id>`, `gh:pr/<n>`, `gh:issue/<n>`, `figma:<fileKey>/<nodeId>`, `url:<url>`, `raw:<path without .md>`, `session:<YYYY-MM-DD>` (what the user said in a session), `repo:<path>` (a file versioned in the monorepo, e.g. `repo:docs/architecture/billing.md`).
- Relevant claims cite their source inline `^[jira:FIN-412]`; the same references go in `sources`.
- Never write a field you cannot infer with reasonable confidence: omit it.

## Reading economy

- **Don't re-read** what this session already holds: pages returned by `PB context`, pages you just wrote, a folder's `README.md` after a search found the page.
- Read the smallest thing that answers: a context pack before single pages, `PB resolve` before the folder lists, one page before its neighbours.
- Batch independent tool calls in one turn.
