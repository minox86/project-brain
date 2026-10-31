# Study — weekly summary for the people who own the product

Status: proposal, not implemented. Date: 2026-10-31.

## Goal

Once a week, the people responsible for the product (Engineering Manager, PMs, tech leads) receive a short summary with three things:
1. **what the brain learned** this week: new decisions, behaviour changes, new concepts;
2. **what is stuck**: open questions with no answer for N days;
3. **active epics with points still under discussion**.

It must reach people where they already look, with no new habit and no new tool.

## What the current tools allow

Verified against the connectors available to the routine:

| Channel | Tool | Can the routine send? |
|---|---|---|
| Teams message | Microsoft 365 connector | **No.** The connector only searches, lists and reads (`teams_list_*`, `chat_message_search`, `read_resource`). |
| Email | Microsoft 365 connector | **No.** Only `outlook_email_search`; there is no send tool. |
| Confluence blog post | `createConfluencePage` with `contentType: "blog"`, `contentFormat: "markdown"` | **Yes.** |
| Confluence page | `createConfluencePage` / `updateConfluencePage` | **Yes.** |
| Jira comment | `addCommentToJiraIssue` (markdown; `commentId` updates an existing comment) | **Yes.** |
| Teams through a webhook (Workflows app) | an HTTP call from the routine | Possible, but needs a secret URL in the routine and network access from the cloud environment. Not verified. |

Teams and email, the most natural channels, cannot be written with today's tools. Confluence and Jira can, and both **already notify people by email and in-app**: watchers of a space hear about new blog posts, watchers of an issue hear about new comments.

## Options

| | A. Confluence blog post | B. Comment on the Jira epic | C. Teams via webhook | D. Digest in the repo only |
|---|---|---|---|---|
| Who receives it | everyone watching the space | watchers and assignee of each epic | the whole channel | whoever opens `brain/digests/` |
| Delivery | Confluence notification (email + in-app) | Jira notification (email + in-app) | Teams post | none |
| Process change | none, if the owners already watch the space; otherwise one click on "Watch" | none | none | people must go and look |
| New setup | a target space | none | a Workflows webhook in the channel, a secret, a network check | none |
| Fits | the overall weekly view | the stuck points of one epic, aimed at the people working on it | maximum visibility | already there |

## Recommendation

**A + B together**, both built only on the Atlassian connector the routine already uses:

- **A** gives the weekly overview: one blog post per week in a chosen space.
- **B** puts the stuck points where the work happens: one comment per active epic that has open questions, so whoever works on it is notified directly.
- **C** is the upgrade if the team wants the summary inside the channel. It needs a webhook created by a channel owner and a check that the cloud routine can reach it: do the spike before promising it.

## Proposed design

### Content (toolkit, deterministic)

A new command, `pb weekly --since <date> [--today <date>]`, with JSON output plus rendered Markdown:

- **Learned**: built from the week's `brain/digests/*.md` ("Ingested" lines) and pages whose `updated` falls in the week, grouped as decisions / features and epics / concepts / modules. One line per page with its summary and a link.
- **Stuck**: open questions not updated for at least `open_question_stale_days` (the same rule as `pb lint`), oldest first, each with what it blocks (`affects`).
- **Epics to watch**: active epics with open questions or `## Constraints and risks`, each with its Jira key and open-question count.
- **Health**: the `pb stats` numbers (pages, words, pages over budget) and the routine problems of the week from the digests.

The toolkit decides **what** to include; the LLM writes only a 2–3 line introduction on top. The rest of the post is passed through verbatim.

### Publishing (routine, once a week)

The routine runs on a cron that may be nightly, so the weekly step needs a guard. `PB state get weekly last` → if 7 days have passed (or the configured weekday has come):

1. `PB weekly --since <last>`. Nothing learned and nothing stuck → publish nothing, record the run.
2. **Blog post** (A): `createConfluencePage`, `contentType: blog`, title `"<Product> brain — week of <date>"`, in `weekly.space`.
3. **Epic comments** (B): for each epic in "Epics to watch" that has open questions, one comment on the Jira epic listing them, each linked to its brain page or context pack. **One rolling comment per epic**: the first time, create it and store its id in `PB state set weekly epic_comments`; after that, update it with `commentId`. The epic's history is not flooded.
4. `PB state set weekly last <today>`; one line in the digest: "Weekly: blog post <link>, N epic comments".

Configuration in `brain/schema/sources.md`: `weekly: {space: <KEY>, weekday: 1, epic_comments: true}`. It is set by a new step in `/pb:routine-setup`, which also tells the owners to **watch** the space (or a parent page) so the post reaches their inbox.

### Rules

- Same privacy rules as the brain: no names, no verbatim messages. The summary says what was decided, not who said it.
- The comments are posted under the routine owner's account. Say so in the comment footer ("posted by the project brain routine").
- The post is a snapshot: it is never updated after publication. The rolling Jira comment is.

## Spikes before building

1. **Blog post through the connector**: publish a test blog post in markdown and check that space watchers get the email notification.
2. **Rolling comment**: add a comment to a test issue, update it with `commentId`, and check whether watchers are notified of the update or only of the first post. If updates are silent, post a new comment only when the list of open questions changes.
3. **Teams webhook (option C)**: create a Workflows webhook in a test channel and try to call it from a cloud routine run (network access, where the secret lives).

## Effort

- `pb weekly` with tests: about half a day.
- Routine step, `/pb:routine-setup` step, state and README: about half a day.
- Spikes: a couple of hours with access to a test space and a test project.
