---
name: routine-setup
description: Configures the nightly routine that feeds the project brain from Microsoft Teams channels, Confluence spaces, Jira epics and merged GitHub PRs — picks channels, spaces and projects, the target branch the routine pushes to without PRs, writes the configuration and generates the cloud routine prompt. Use when the user (typically the Engineering Manager) wants to set up, change or check the brain's periodic ingestion or routine.
argument-hint: "[show | schedule <frequency>]"
---

# /pb:routine-setup — configure the nightly routine

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Repo mode only.

**Connectors:** check those this run needs before starting (see **Connectors** in the conventions) and guide the user to connect what is missing. Setup needs Microsoft 365 (Teams), Atlassian (Confluence, Jira), `gh` and, to create the routine, the `schedule` skill. The routine itself runs with the connectors of the account that creates it: the same ones must be connected there.

`schedule <frequency>`: change only how often the routine runs — go to **6. Schedule** with the given frequency, then update `routine.schedule` in `brain/schema/sources.md`, update the cloud routine (step 8, update instead of create) and commit. Stop there.

`show`: print the current `routine`, `teams`, `confluence`, `jira`, `github` configuration from `brain/schema/sources.md` and the cursors (`PB state get teams|confluence|jira|github`), then stop.

## 1. Owner

The routine is a Claude Code cloud routine that runs with the account of whoever creates it — normally the **Engineering Manager**. Commits are attributed to that account, and it only sees the Teams channels and Confluence spaces that account can access. Confirm the user is the intended owner.

## 2. Teams channels

With the Microsoft 365 connector: `teams_list_teams`, then `teams_list_channels` for the teams the user names. Show them numbered and let the user pick the channels where the team (developers, PMs, designers, analysts, QA) discusses the product. Check each one is readable (`teams_list_channel_messages` with a small page); drop and report the ones that fail.

## 3. Confluence spaces

With the Atlassian connector: `getConfluenceSpaces`. Let the user pick the spaces where analyses and requirements are written, optionally restricted to a page tree (root page id). Check read access with one CQL search per space.

## 3b. Jira projects

With the Atlassian connector: `getVisibleJiraProjects`. Let the user pick the projects whose epics the brain should follow: the routine keeps their `epic` pages aligned with Jira and closes them when the epic is done. Check read access with one JQL search per project (`project = <KEY> AND issuetype = Epic`).

## 4. GitHub repo

`git remote get-url origin` → `owner/name`. Confirm.

## 5. Target branch

The routine commits and pushes **directly, without a PR**, to one branch. Explain and let the user choose:
- **default branch (`main`)** — knowledge lands immediately and CI regenerates index and context packs at once; the owner's account must be allowed to push to it past branch protection (a bypass for this account, or a ruleset exception for `brain/**`). Check with the user that this is in place.
- **a long-lived branch** (e.g. `brain/inbox`) — no protection to bypass; someone merges it into `main` when they want, and that merge is the only review point.

## 6. Schedule

Ask how often the routine should run, offering plain-language options and turning the answer into a cron expression (times in the routine's timezone):

| Option | Cron |
|---|---|
| Every night at 02:00 (recommended) | `0 2 * * *` |
| Every night, weekdays only | `0 2 * * 1-5` |
| Three times a working day (08:00, 13:00, 18:00) | `0 8,13,18 * * 1-5` |
| Every N hours (N ≥ 1) | `0 */N * * *` |
| Once a week (Monday 06:00) | `0 6 * * 1` |
| Custom | the user's cron |

Routines run at most once an hour: the minute field must be a single number. `PB validate` rejects other schedules (`bad-schedule`). More frequent runs ingest sooner but cost more and often meet threads still being discussed, which are deferred anyway. For anything in between, `/pb:routine-run` starts a run on demand.

## 7. Write the configuration

Edit the frontmatter of `brain/schema/sources.md`:

    routine: {branch: <branch>, schedule: "<cron>", owner_role: Engineering Manager, trigger_id: <id, after step 8>}
    teams:
      - {id: <slug>, team: "<team name>", team_id: "<id>", channel: "<channel name>", channel_id: "<id>"}
    confluence:
      - {id: <slug>, space: <KEY>, root_page: "<id or omit>"}
    jira:
      - {id: <slug>, project: <KEY>}
    github: {repo: <owner/name>}

Replace the `## Routine` section of `brain/AGENTS.md` with: owner role, schedule, target branch, the list of channels, spaces and Jira projects, and "digests in `brain/digests/`".

Validate, then the closing flow (`PB commit -m "pb(routine-setup): configure nightly routine"`). The routine reads this configuration from the target branch: make sure the commit reaches it (merge the PR, or push to the target branch).

## 8. Create the routine

Render `BASE/../../templates/routine/prompt.md`, replacing `{{branch}}`, `{{repo}}`, `{{channels}}`, `{{spaces}}`, `{{projects}}`.

**If you can manage routines here** (Claude Code with the `schedule` skill or the remote-trigger tool): create the routine yourself on the monorepo `<repo>`, with the rendered prompt, the schedule `<cron>` and the Microsoft 365 and Atlassian connectors. When `routine.trigger_id` already exists, update that routine instead of creating a new one. Relay the routine's link and next run time. Write the routine id to `routine.trigger_id` in `sources.md` and commit it (`PB commit -m "pb(routine-setup): record routine id"`).

**Otherwise** give the user the steps:
1. Run `/schedule` in Claude Code (or open claude.ai/code/routines) and create a routine on the monorepo `<repo>` with schedule `<cron>`.
2. Paste the rendered prompt.
3. Enable the Microsoft 365 and Atlassian connectors for the routine and make sure the `pb` plugin is installed for the account.
4. Tell you the routine id, so it can be recorded in `routine.trigger_id`.

Either way, finish with a first run: `/pb:routine-run`, then check `brain/digests/<today>.md` on the target branch.
