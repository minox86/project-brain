---
routine: null
teams: []
confluence: []
github: null
jira: []
---
# Sources

External sources the brain ingests. Configured by `/pb:routine-setup`; edited by hand only with care.

- `routine`: `{branch, schedule, owner_role, trigger_id}` — target branch the routine pushes to (no PR), cron schedule (at most hourly), role of the account that owns the routine, id of the cloud routine (used by `/pb:routine-run`).
- `teams`: list of `{id, team, team_id, channel, channel_id}` — channels where the team discusses the product.
- `confluence`: list of `{id, space, root_page}` — spaces (optionally a page tree) where analyses and requirements are written.
- `github`: `{repo}` — `owner/name` of the monorepo, for merged-PR ingestion.
- `jira`: list of `{id, project}` — projects whose epics the brain follows (`epic` pages, synced by the routine); features may also reference their keys.
