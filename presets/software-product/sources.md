---
routine: null
review: null
teams: []
confluence: []
github: null
jira: []
meetings: []
questions: null
---
# Sources

External sources the brain ingests. Configured by `/pb:routine-setup`; edited by hand only with care.

- `routine`: `{branch, schedule, owner_role, trigger_id}` — branch the routine pushes to (`docs/brain`, with its PR "Brain updates" to the default branch), cron schedule (at most hourly), role of the account that owns the routine, id of the cloud routine (used by `/pb:routine-run`).
- `review`: `{schedule, trigger_id}` — the weekly review routine (`/pb:review --auto` on `docs/brain`): weekly cron schedule, id of its cloud routine. `null`: no weekly review; `/pb:review` is still run by hand.
- `teams`: list of `{id, team, team_id, channel, channel_id}` — channels where the team discusses the product.
- `confluence`: list of `{id, space, root_page}` — spaces (optionally a page tree) where analyses and requirements are written.
- `github`: `{repo}` — `owner/name` of the monorepo, for merged-PR ingestion.
- `meetings`: list of `{id, subject, organizer}` — recurring Teams meetings (refinement, design review, demo…) ingested after each occurrence; `subject` is matched against the event subject, `organizer` is the organizer's email.
- `jira`: list of `{id, project}` — projects whose epics and issues the brain reads as a source; features carry their keys in `jira`.
- `questions`: `{team, team_id, channel, channel_id}` — the Teams channel where the routine posts each new open question, once, as a message people answer by replying; the routine reads the replies and writes the answer in the brain. `null`: off. Optional: `max_per_run` (cards posted per run, default 5, oldest questions first), `areas` (only questions of these areas: `functional`, `ux`, `technical`), `people` (who is tagged on the card, by role: `{tech: [...], product: [...], analyst: [...], ux: [...]}`, each a list of Teams sign-in addresses `name@company.com` or of `{name, email}`; the card always names the roles that can answer — Tech for a `technical` question, Product and Analyst for a `functional` one, UX for a `ux` one — and tags the people listed for them), `webhook_env` (name of the environment variable that holds the webhook, default `PB_QUESTIONS_WEBHOOK`). **The webhook URL of the Teams workflow is a secret and is never written here**, nor anywhere in the repo: it is read from that environment variable (the cloud routine's environment) or from `git config --local pb.questionsWebhook` (a clone). Without it nothing is posted. Set up by `/pb:routine-setup questions`.
