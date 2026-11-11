---
routine: null
teams: []
confluence: []
github: null
jira: []
meetings: []
---
# Sources

External sources the brain ingests. Configured by `/pb:routine-setup`; edited by hand only with care.

- `routine`: `{branch, schedule, owner_role, trigger_id}` — branch the routine pushes to (`docs/brain`, with its PR "Brain updates" to the default branch), cron schedule (at most hourly), role of the account that owns the routine, id of the cloud routine (used by `/pb:routine-run`).
- `teams`: list of `{id, team, team_id, channel, channel_id}` — channels where the team discusses the product.
- `confluence`: list of `{id, space, root_page}` — spaces (optionally a page tree) where analyses and requirements are written.
- `github`: `{repo}` — `owner/name` of the monorepo, for merged-PR ingestion.
- `meetings`: list of `{id, subject, organizer}` — recurring Teams meetings (refinement, design review, demo…) ingested after each occurrence; `subject` is matched against the event subject, `organizer` is the organizer's email.
- `jira`: list of `{id, project}` — projects whose epics the brain follows (`epic` pages, synced by the routine); features may also reference their keys.
