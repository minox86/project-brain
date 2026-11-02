---
name: meeting
description: Feeds the project brain with a Microsoft Teams meeting — reads event, transcript and chat through Microsoft 365, and turns them into decisions, open questions and feature or concept updates, without storing the transcript. Use when the user asks to add or ingest a meeting ("save the refinement we just had", "ingest today's design review"), or pastes a teams.microsoft.com meeting link.
argument-hint: "[last | today | <teams link> | <meeting name>]"
---

# /pb:meeting — ingest a Teams meeting

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only.

Recurring meetings configured in `/pb:routine-setup` (the `meetings:` list in `brain/schema/sources.md`) are ingested by the routine after each occurrence: use this skill for one-off meetings, or to ingest an occurrence right away. If the meeting is an occurrence of a configured series, after writing, move that series' cursor past it (`PB state set meetings <id> …`) only if it is the oldest unprocessed one, so the routine does not ingest it twice.

## 1. Find the meeting

Microsoft 365 connector:
- `<link>`: search the calendar for the event with that join URL;
- `last` (default): the most recent meeting that has ended today;
- `today`: list today's ended meetings with time and title, and let the user pick one or more;
- `<name>`: `outlook_calendar_search` by subject over the last 14 days; ask if ambiguous.

If the Microsoft 365 connector is missing or not signed in, guide the user as **Connectors** in the conventions says before anything else. As a fallback offer to work from notes or a transcript the user pastes.

## 2. Read

Read the transcript and the meeting chat with `read_resource` (resources linked from the event). With subagents available, dispatch one reader (`BASE/../../references/reader.md`, model `sonnet`) for the occurrence instead, and work from its findings: the transcript stays out of this session. No transcript available: say so and offer to work from the user's notes instead (then use `/pb:put`).

## 3. Extract

From the transcript and chat, keep only what passes the **significance gate**:
- decisions (functional, UX, technical) with options considered and reasons;
- open questions left unresolved, and action-blocking doubts;
- scope agreements, constraints and risks of an epic in progress (on its `epic` page), changes to expected behaviour of features, new or clarified domain concepts, discoveries about modules and interfaces.

Drop: status updates, scheduling, small talk, who-will-do-what (that belongs to Jira), opinions about people.

**No raw**: the transcript and chat are never written to the brain. Cite `teams:meeting/<event id>` in `sources` and inline.

## 4. Plan, write, close

Show the plan (page · create/update · what) and wait for confirmation. Write following the writing rules; link decisions to the features/modules they affect; set `resolved_by` on open questions answered in the meeting. Closing flow: `PB save -m "pb(meeting): <meeting title> <date>" <files written>`.
