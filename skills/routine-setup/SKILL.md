---
name: routine-setup
description: Configures the nightly routine that feeds the project brain from Microsoft Teams channels, Confluence spaces and merged GitHub PRs — picks channels and spaces, the target branch the routine pushes to without PRs, writes the configuration and generates the cloud routine prompt. Use when the user (typically the Engineering Manager) wants to set up, change or check the brain's periodic ingestion or routine.
argument-hint: "[show]"
---

# /pb:routine-setup — configure the nightly routine

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Repo mode only.

`show`: print the current `routine`, `teams`, `confluence`, `github` configuration from `brain/schema/sources.md` and the cursors (`PB state get teams|confluence|github`), then stop.

## 1. Owner

The routine is a Claude Code cloud routine that runs with the account of whoever creates it — normally the **Engineering Manager**. Commits are attributed to that account, and it only sees the Teams channels and Confluence spaces that account can access. Confirm the user is the intended owner.

## 2. Teams channels

With the Microsoft 365 connector: `teams_list_teams`, then `teams_list_channels` for the teams the user names. Show them numbered and let the user pick the channels where the team (developers, PMs, designers, analysts, QA) discusses the product. Check each one is readable (`teams_list_channel_messages` with a small page); drop and report the ones that fail.

## 3. Confluence spaces

With the Atlassian connector: `getConfluenceSpaces`. Let the user pick the spaces where analyses and requirements are written, optionally restricted to a page tree (root page id). Check read access with one CQL search per space.

## 4. GitHub repo

`git remote get-url origin` → `owner/name`. Confirm.

## 5. Target branch

The routine commits and pushes **directly, without a PR**, to one branch. Explain and let the user choose:
- **default branch (`main`)** — knowledge lands immediately and CI regenerates index and context packs at once; the owner's account must be allowed to push to it past branch protection (a bypass for this account, or a ruleset exception for `brain/**`). Check with the user that this is in place.
- **a long-lived branch** (e.g. `brain/inbox`) — no protection to bypass; someone merges it into `main` when they want, and that merge is the only review point.

## 6. Schedule

Default `0 2 * * *` (02:00 every night, in the routine's timezone). Minimum interval for routines is one hour.

## 7. Write the configuration

Edit the frontmatter of `brain/schema/sources.md`:

    routine: {branch: <branch>, schedule: "<cron>", owner_role: Engineering Manager}
    teams:
      - {id: <slug>, team: "<team name>", team_id: "<id>", channel: "<channel name>", channel_id: "<id>"}
    confluence:
      - {id: <slug>, space: <KEY>, root_page: "<id or omit>"}
    github: {repo: <owner/name>}

Replace the `## Routine` section of `brain/AGENTS.md` with: owner role, schedule, target branch, the list of channels and spaces, and "digests in `brain/digests/`".

Validate, then the closing flow (`PB commit -m "pb(routine-setup): configure nightly routine"`). The routine reads this configuration from the target branch: make sure the commit reaches it (merge the PR, or push to the target branch).

## 8. Create the routine

Render `BASE/../../templates/routine/prompt.md`, replacing `{{branch}}`, `{{repo}}`, `{{channels}}`, `{{spaces}}`. Then give the user the steps:
1. In Claude Code run `/schedule` (or open claude.ai/code/routines) and create a routine on the monorepo `<repo>` with schedule `<cron>`.
2. Paste the rendered prompt.
3. Make sure the Microsoft 365 and Atlassian connectors are enabled for the routine and the `pb` plugin is installed for the account.
4. Run it once now ("Run now") and check `brain/digests/<today>.md` on the target branch.
