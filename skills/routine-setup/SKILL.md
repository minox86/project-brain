---
name: routine-setup
description: Configures the two routines of the project brain — the nightly one that feeds it from Microsoft Teams channels and recurring meetings, Confluence spaces, Jira epics and merged GitHub PRs, and the weekly review that keeps it clean — picks channels, spaces and projects, optionally sets up the posting of open questions to a Teams channel through a workflow webhook, writes the configuration and generates the cloud routine prompts. Use when the user (typically the Engineering Manager) wants to set up, change or check the brain's periodic ingestion, its weekly review or its routines, or wants the brain's open questions asked on Teams (add, change or remove the Teams webhook).
argument-hint: "[show | schedule <frequency> | review [<frequency> | off] | questions [off]]"
---

# /pb:routine-setup — configure the nightly routine

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

**Connectors:** check those this run needs before starting (see **Connectors** in the conventions) and guide the user to connect what is missing. Setup needs Microsoft 365 (Teams), Atlassian (Confluence, Jira), `gh` and, to create the routine, the `schedule` skill. The routine itself runs with the connectors of the account that creates it: the same ones must be connected there.

`schedule <frequency>`: change only how often the routine runs — go to **6. Schedule** with the given frequency, then update `routine.schedule` in `brain/.pb/schema/sources.md`, update the cloud routine (step 8, update instead of create) and save (step 9). Stop there.

`review [<frequency> | off]`: set up, reschedule or remove only the weekly review — go to **6b. Weekly review**, then update `review` in `brain/.pb/schema/sources.md` and the `## Routine` section of `brain/AGENTS.md`, create, update or delete its cloud routine (step 8) and save (step 9). Stop there.

`questions [off]`: set up, change or remove only the posting of open questions on Teams, at any time after the routine exists — go to **6c. Questions on Teams**, then update `questions` in `brain/.pb/schema/sources.md` and the `## Routine` section of `brain/AGENTS.md`, update the cloud routine's prompt (step 8, update instead of create: older prompts do not name the `questions` source) and save (step 9). Stop there.

`show`: print the current `routine`, `review`, `teams`, `meetings`, `confluence`, `jira`, `github`, `questions` configuration from `brain/.pb/schema/sources.md`, the cursors (`PB state get teams|meetings|confluence|jira|github`), when the review last ran (`PB state get review last`) what waits for a decision (`PB pending`: `waiting`) and, with `questions` set, `PB questions` (cards waiting for an answer, questions not posted yet, whether this clone has the webhook), then stop.

## 1. Owner

The routine is a Claude Code cloud routine that runs with the account of whoever creates it — normally the **Engineering Manager**. Commits are attributed to that account, and it only sees the Teams channels and Confluence spaces that account can access. Confirm the user is the intended owner.

## 2. Teams channels

With the Microsoft 365 connector: `teams_list_teams`, then `teams_list_channels` for the teams the user names. Show them numbered and let the user pick the channels where the team (developers, PMs, designers, analysts, QA) discusses the product. Check each one is readable (`teams_list_channel_messages` with a small page); drop and report the ones that fail.

## 2b. Recurring meetings

With the Microsoft 365 connector: `outlook_calendar_search` over the last 30 days (`query: "*"`, paginate). Keep Teams meetings that occur at least twice with the same subject and organizer, and show them numbered with their cadence (e.g. "Sprint refinement — weekly, Tue"). Let the user pick the ones where product decisions are taken (refinement, design review, demo, architecture review); one-to-ones and stand-ups usually fail the significance gate.

For each pick, read the latest occurrence and check that its transcript is readable (`meetingTranscriptUrl` with `read_resource`). If it is not, tell the user what is needed:
- **transcription on** for the series (the organizer can set "record and transcribe automatically" in the meeting options);
- the **routine owner's account invited** to the series, since the routine reads with that account.

Keep the series anyway if the user will fix it; the routine skips occurrences without a transcript and says so in the digest.

## 3. Confluence spaces

With the Atlassian connector: `getConfluenceSpaces`. Let the user pick the spaces where analyses and requirements are written, optionally restricted to a page tree (root page id). Check read access with one CQL search per space.

## 3b. Jira projects

With the Atlassian connector: `getVisibleJiraProjects`. Let the user pick the projects whose epics and issues the brain reads as a source: the routine keeps what lasts on the features they deliver and their keys in the features' `jira`. Check read access with one JQL search per project (`project = <KEY>`).

## 4. GitHub repo

`git remote get-url origin` → `owner/name`. Confirm.

## 5. Target branch

The routine is the only writer on the fixed branch `docs/brain` (`routine.branch: docs/brain`) and keeps one PR from it to the default branch, "Brain updates", with the area reviewers on the watched changes it carries. Nothing merges by itself: the maintainer brings its changes to the default branch with `/pb:merge`. Check with `gh`, never ask what it can tell (`gh api repos/<repo>/rules/branches/docs/brain`, empty when nothing covers it): `docs/brain` must accept pushes from the routine owner and from whoever runs `/pb:merge`. If a ruleset or a protection pattern (e.g. `docs/*`, `*`) covers it, propose excluding `docs/brain` from it; only a repo admin can change it: apply it with `gh api` if the user is one (`gh api repos/<repo> --jq .permissions.admin`), otherwise give the user the line for an admin. The routine's account must be able to push to `docs/brain` and open PRs.

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

## 6b. Weekly review

Offer the weekly review: a second routine that reads the whole brain once a week, fixes by itself what has one right answer (duplicated facts, content on the wrong page, superseded versions, terms that differ from the glossary, feature status behind Jira, schema errors, pages over budget) and queues the rest for a person, who settles it with `/pb:review`. It collects no news and needs only the Atlassian connector (Jira). Recommended once the brain has a few dozen pages.

Schedule: once a week, away from the nightly run. Default **Sunday at 04:00** (`0 4 * * 0`); the user may give another cron that runs at most once a week — one hour, on one weekday (`0 4 * * 0`) or one day of the month (`0 4 1 * *`) — and `PB validate` refuses any other (`bad-schedule`). More often than weekly costs a full read of the brain each time and finds little.

Declined, or `review off`: no `review` in `sources.md`; delete the review's cloud routine if `review.trigger_id` exists. The owner can still run the same review by hand with `/pb:review`.

## 6c. Questions on Teams (optional)

Offer it; it can also be added later with `/pb:routine-setup questions`. The routine posts each new open question once to a Teams channel, as a card that says what it blocks, what is known and which role can answer (Tech, Product, Analyst, UX, from the question's area), tagging the people of that role when the team lists them; people answer by replying to the card; the next run writes the answer in the brain (a decision or a fact), deletes the question and sends the change to its reviewers on "Brain updates". Posting goes through a **Teams workflow webhook**; reading the replies uses the Microsoft 365 connector the routine already has.

1. **Channel.** Pick it as in step 2 (`teams_list_teams`, `teams_list_channels`). Recommend a channel of its own (e.g. "Brain questions") that the people who can answer follow: cards in a busy channel get lost. It may also be one of the ingested channels. Check it is readable by the routine owner's account (`teams_list_channel_messages`).
2. **Workflow.** The user creates it in Teams, once: on the channel, **⋯ → Workflows**, the template that posts to a channel when a webhook request is received ("Send webhook alerts to a channel" in current Teams), pick the team and the channel, save, and copy the URL it gives. Whoever creates it owns it: if they leave, it must be created again.
3. **The URL is a secret**: whoever has it can post to the channel. It never goes in `sources.md`, in any file of the repo, or in this chat. Tell the user where to put it, and let them do it:
   - **the cloud routine**: an environment variable `PB_QUESTIONS_WEBHOOK` in the environment the routine runs in (claude.ai/code, the routine's environment settings). When that environment restricts network access, the webhook's host (the host of the URL, e.g. `….logic.azure.com` or `….api.powerplatform.com`) must be among the allowed domains;
   - **this clone**, for `/pb:routine-run --local`, `/pb:sync` and the test below: `! git config --local pb.questionsWebhook '<url>'` — it stays in `.git/config`, which is never pushed. Optional: without it, only the scheduled routine posts.
   If the user pastes the URL in the chat anyway, do not repeat it and do not write it anywhere: give them the command to run themselves, and suggest creating the workflow again if the conversation is shared.
4. **Settings**, each with its default: how many cards per run (`max_per_run`, 5: on the first run a brain with many open questions would flood the channel; the oldest go first, the rest follow run by run); only some areas (`areas`, default all); **who is tagged** (`people`): ask who covers each role — Tech, Product, Analyst, UX — and write their Teams sign-in addresses (`people: {tech: [name@company.com], product: [...], analyst: [...], ux: [...]}`; `{name: "…", email: …}` when the name to show differs from the address). A role left out is named on the card without tagging anyone; the people tagged must be members of the channel's team to be notified. Offer the candidates you can see (the `reviewers` of `brain/.pb/schema/review.md` are GitHub handles, not addresses: use them only to ask "is it the same people?"); another name for the environment variable (`webhook_env`), when the team's rules ask for one.
5. **Test**, once `questions` is written (step 7) and when this clone has the webhook: `PB questions test` posts a sample card. `posted: true` → ask the user to check that it arrived in the right channel and that replying to it is allowed. An error → relay it: 4xx usually means a wrong or deleted workflow, "could not reach" a network that blocks the host. Without the webhook in this clone, say that the first scheduled run is the test: its digest lists the questions asked under "Questions", or the failure under "Problems".

`questions off`: set `questions: null`. Nothing is posted and no reply is read any more; the cards already posted stay in Teams. Tell the user to delete the workflow in Teams and remove the variable from the routine's environment (and `git config --local --unset pb.questionsWebhook`).

Changing the webhook later (a new workflow, a new channel): the same steps; only the variable changes, and `questions` in `sources.md` when the channel does.

## 7. Write the configuration

Edit the frontmatter of `brain/.pb/schema/sources.md`:

    routine: {branch: docs/brain, schedule: "<cron>", owner_role: Engineering Manager, trigger_id: <id, after step 8>}
    review: {schedule: "<weekly cron>", trigger_id: <id, after step 8>}   # omit when the weekly review is declined
    teams:
      - {id: <slug>, team: "<team name>", team_id: "<id>", channel: "<channel name>", channel_id: "<id>"}
    confluence:
      - {id: <slug>, space: <KEY>, root_page: "<id or omit>"}
    jira:
      - {id: <slug>, project: <KEY>}
    meetings:
      - {id: <slug>, subject: "<series subject>", organizer: <organizer email>}
    github: {repo: <owner/name>}
    questions: {team: "<team name>", team_id: "<id>", channel: "<channel name>", channel_id: "<id>", max_per_run: 5, people: {tech: [<address>], product: [<address>]}}   # null when declined; `people` optional; never the webhook URL

Replace the `## Routine` section of `brain/AGENTS.md` with: owner role, schedule, the list of channels, recurring meetings, spaces and Jira projects, "digests in `brain/.pb/digests/`" and, with the weekly review, its schedule, "review reports in `brain/.pb/digests/<date>-review.md`" and "what waits for a decision is settled with `/pb:review`"; with questions on Teams, "open questions are asked in <team> / <channel>: answer by replying to the card".

Cloud routines do not load plugins: the routines follow the copy of the toolkit and of their instructions (sync, put, meeting and review skills and the references) vendored in `brain/.pb/toolkit/`. Refresh it from this plugin with `PB toolkit-sync`, so the routine runs the same version as the plugin.

Do not save yet: step 9 saves everything at once, routine ids included.

## 8. Create the routines

Render `BASE/../../templates/routine/prompt.md`, replacing `{{branch}}`, `{{repo}}`, `{{channels}}`, `{{spaces}}`, `{{projects}}`, `{{meetings}}`.

**If you can manage routines here** (Claude Code with the `schedule` skill or the remote-trigger tool): create the routine yourself on the monorepo `<repo>`, with the rendered prompt, the schedule `<cron>` and the Microsoft 365 and Atlassian connectors. When `routine.trigger_id` already exists, update that routine instead of creating a new one. Relay the routine's link and next run time. Write the routine id to `routine.trigger_id` in `sources.md`. With questions on Teams, remind the user of step 6c.3: the routine posts only once `PB_QUESTIONS_WEBHOOK` is set in its environment; you cannot set it for them and must never be given its value.

**Otherwise** give the user the steps:
1. Run `/schedule` in Claude Code (or open claude.ai/code/routines) and create a routine on the monorepo `<repo>` with schedule `<cron>`.
2. Paste the rendered prompt.
3. Enable the Microsoft 365 and Atlassian connectors for the routine. The `pb` plugin is not needed there: the routine follows the instructions vendored in `brain/.pb/toolkit/`.
4. With questions on Teams: set `PB_QUESTIONS_WEBHOOK` in the routine's environment (step 6c.3).
5. Tell you the routine id, so it can be recorded in `routine.trigger_id`.

**The weekly review**, when chosen in 6b: a second routine, created the same way on the same monorepo. Render `BASE/../../templates/routine/review-prompt.md`, replacing `{{branch}}` (`routine.branch`, or `docs/brain` when only the review is set up) and `{{repo}}`; schedule `review.schedule`; the Atlassian connector only. Write its id to `review.trigger_id`; when it already exists, update that routine instead of creating a new one.

## 9. Save

Validate, then the closing flow: `PB save brain/.pb/schema/sources.md brain/AGENTS.md <every changed file under brain/.pb/toolkit/>`. Changes under `.pb/schema/` and `.pb/toolkit/` are always watched, so the PR that carries them asks the reviewers. The routine reads configuration and instructions from `docs/brain`, which starts from the default branch: it works once that PR is merged (if `docs/brain` is behind, after `/pb:merge`). Say: "Commit these files and merge their PR (or ask <reviewers>), then run `/pb:routine-run` for a first run." After every plugin upgrade, `PB toolkit-sync` and save again, or the routine keeps following the old instructions.
