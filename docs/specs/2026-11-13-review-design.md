# project-brain — `/pb:review`: weekly unattended review and the owner's decisions (0.7)

Status: draft for approval, owner's answers of 2026-11-13 included · 2026-11-13 · replaces the skills `/pb:lint` and `/pb:questions`.

Lines marked **(call)** are choices made while writing this document, not decisions of the product owner:
check them while reading.

## 1. Intent

The nightly routine adds knowledge to the brain. Nothing keeps the whole of it clean over time: pages
written on different days repeat each other, drift apart, keep superseded versions, use different words
for one concept. Today the only tools are `/pb:lint --fix` (interactive, limited to the structural findings
of `PB lint`) and `/pb:questions` (interactive, open questions only). Both wait for someone to remember
them, and both ask the person about things a careful reader could settle alone.

Another team keeps a Confluence knowledge base healthy with a weekly unattended job that compares all pages
against each other, fixes what has one right answer, and reports what needs a human. This design takes that
method (not its project specifics) and splits the work in two halves of one procedure:

- a **weekly unattended routine** fixes by itself everything it can settle with confidence, and queues the
  rest;
- an **interactive command**, run by the repo owner now and then, walks through the queue and asks only
  what matches the person's competence.

## 2. Goals, non-goals, anti-goals

**Goals**

- One procedure, `/pb:review`, with two modes: unattended (the weekly routine) and interactive (the owner).
- The unattended mode never asks and never guesses: a change is applied only when the brain, its sources or
  Jira settle it; otherwise it is queued.
- The interactive mode asks one thing up front — functional competence, technical, or both — and then only
  the queued items of those areas, one at a time, with suggested answers.
- Every change of a review run is reported numbered and tagged, with before, after and why, so a reviewer
  can read the run without reading the diff. In an interactive session the owner can ask to revert a
  change of that session by its number. Changes of the unattended routine are contested where every other
  change is: on the Brain updates PR, before it is merged.
- `/pb:lint` and `/pb:questions` disappear as skills; what they did is inside `/pb:review`.

**Non-goals**

- Collecting news: the weekly routine reads no Teams, Confluence or meeting content. It reads the brain,
  the repo (module paths) and Jira (feature status, keys).
- Changing the nightly routine. Four improvements found in the same comparison (source content treated as
  data, a short human summary in the digest, numbered changes, cleaning superseded content met while
  editing) are a separate, later piece of work.
- The weekly summary for product owners (`docs/studies/weekly-summary.md`): communication, not cleaning.
- Changing `PB review` (watched points and reviewers) or `review.md`. The name clash is accepted: in prose,
  the skill is "the review", the toolkit command is "the watched points".

**Anti-goals**

- A review that invents facts, picks a side of a contradiction without evidence, or rewrites a decision.
- A review that deletes pages unattended.
- A queue nobody empties because it mixes everything: each item carries its area so each person sees only
  their own.

## 3. What the review does

### 3.1 Rules (both modes)

Adapted from the other team's rules to a brain that lives in git and has a typed schema.

1. **No duplication.** A fact lives on its canonical page (the page whose type and title own the topic);
   elsewhere it becomes a link, or is removed when the reader does not need the pointer.
2. **No contradictions.** When two pages or sections disagree, resolve using, in order: the most recent
   accepted decision; the page that owns the topic, when the other page only repeats it. Not resolvable
   with confidence → queue it, change nothing. The unattended mode does not open the cited Teams,
   Confluence or meeting sources to settle it **(call)**; the interactive mode may, as `/pb:questions`
   does today, to prepare its suggested answers.
3. **Content where it belongs.** Move content to the page that owns the topic. A new page only when the
   type's prose allows one and no page covers it (`PB resolve`).
4. **Latest version only.** Pages describe the current state: remove superseded versions, "previously…"
   notes, dated or "update" sections, v1/v2 side by side, stale next steps.
5. **Decisions are the exception.** Never rewritten or deleted. A decision the sources clearly show as
   overridden gets `status: superseded` and the new one `supersedes`, as `writing.md` already says; links to
   a superseded decision are repointed to its successor.
6. **The glossary is the vocabulary.** The `concept` pages are the glossary. Other pages use the concept's
   title; synonyms and variant spellings found elsewhere are replaced with it and added to the concept's
   `aliases`; translations go to its `term_<lang>` fields, as the type says. Definitions repeated on other pages are removed. Two concepts that mean the
   same thing are a merge (queued, see 3.3). A term used with a specific meaning on two or more pages and
   without a concept page is queued as a proposed concept (creating one is a watched point).
7. **Aligned with Jira.** A feature whose Jira work is released gets `status: released`; a feature's `jira`
   keys that no longer exist are queued. Nothing else is copied from Jira (**Work in Jira** in `writing.md`).
8. **Quality.** Short sentences, active voice, no filler, no repetition, the body structure of the type.
   Meaning stays intact.
9. **Historical records stay.** Digests, `.pb/raw/` extracts, `.pb/corrections.md` and the body of
   decisions are never edited.
10. **Structural findings.** Everything `PB lint` reports is in scope: schema errors, broken links,
    over-budget pages, duplicate candidates, orphans, stale open questions, archivable items, dead module
    paths, references to superseded decisions.

### 3.2 Applied unattended

Applied by the routine without asking, when the evidence is explicit (confidence **high** in the sense of
`writing.md`):

- schema errors and broken links with one evident correction; references to superseded decisions;
- over-budget pages condensed; rule 4 and rule 8 edits;
- rule 1 when the canonical page already states the fact (the copy goes);
- rule 3 moves between existing pages;
- rule 6 term replacements and `aliases`;
- rule 7 `status: released`;
- module `paths` updated when the repo shows where the files moved (a rename with the same content);
- an orphan linked from the page it evidently belongs to;
- an open question the brain now answers explicitly (an accepted decision or a canonical page states the
  answer): `status: resolved` with `resolved_by` when a decision answers it, otherwise the answer's page is
  cited under `## Known so far` and the item is queued for confirmation.

Changes on watched points are still named on the PR with their reviewers: that mechanism is untouched.

### 3.3 Queued for a person

Never applied unattended:

- any deletion or merge of pages (duplicate candidates, concept merges, archivable items, orphans with no
  evident home, modules whose paths are gone);
- contradictions rule 2 cannot settle;
- every change the routine would rate medium or low;
- proposed new concepts;
- open questions, which are the queue's oldest members.

The queue has two forms **(call)**:

- **Knowledge doubts** — two pages or sources disagree on what is true — are `open-question` pages, as
  today: both versions cited, `area` set, `affects` linking the pages. They are knowledge about the product.
- **Maintenance doubts** — merge, delete, move, a proposed concept, a dead Jira key — are lines in
  `brain/.pb/pending.md`, so the brain is not filled with questions that are not about the product:

      - [ ] R<n> · <functional|technical|any> · <TAG> · <page titles> · <the doubt, with both versions or
        the proposed action> · suggested: <action, or none> · found: <YYYY-MM-DD>

  `n` is the last number given + 1, remembered in the file (`<!-- last: R<n> -->`) so that the number of a removed
  item is never given again (without the note: the highest number in the file, malformed lines included); two lines never share a number
  (`bad-pending`). A run does not queue again an item already there (same tag and pages).
  An open item whose cause is gone (the page was fixed by someone) is removed by the next run.

  **A "no" is remembered (call).** When the owner answers "leave it as it is" (these are not duplicates,
  keep this page), the line stays, ticked, with the reason: `- [x] R<n> · … · kept: <reason>`. Ticked lines
  are the review's suppression list: no run queues or applies that item again. The same line is written
  when the owner reverts a change of the review. Ticked lines are never removed by a run.

Area of an item: the area of the pages involved, as the watched points already compute it (the page's own
`area` when it has one, as decisions and open questions do, otherwise its type's); `ux` counts as
functional **(call)**; pages of different areas give `any`, which is asked to everyone.

### 3.4 The report

Every review run, unattended or interactive, writes `brain/.pb/digests/YYYY-MM-DD-review.md`:

    # Review YYYY-MM-DD
    <pages read, pages edited, created, queued items added / removed, open questions closed>
    ## Needs a decision
    - R<n> | <open question title> · <area> · <one line>
    ## Changes
    ### <page title>
    - <k.j> <TAG> · <section>: <before, short excerpt> → <after> · <why>
    ## Suggestions
    - <structural improvements not applied: a page to split, a missing owner, a schema proposal>
    ## Problems

Tags: `DUPLICATE`, `CONTRADICTION`, `MOVED`, `OUTDATED`, `SUPERSEDED` (decision), `GLOSSARY`, `QUALITY`,
`LINK`, `SCHEMA`, `JIRA`. Pure wording edits and term replacements on one page are one line. With nothing
to fix, the report says so in two lines. "Needs a decision" comes first, because it is what a person must
act on.

The description of the Brain updates PR gets one line: the count of queued items per area (open lines of
`pending.md` plus open questions) and the path of the latest report. Every `routine finish` rebuilds that
description, the nightly one included, so the toolkit computes the line: `pending.md` is parsed by the
toolkit and its format checked by `PB validate`.

`PB validate` reports a malformed queue whatever its scope, because CI and routine runs validate pages only.
The routine appends to the queue on `docs/brain` while a person answers in a branch, so the file conflicts
in `/pb:merge`: `PB merge start` settles it alone (both sides' items; an answered item stays removed, a
ticked one stays ticked, a number shared by two items is reassigned).

Review reports follow `digest_retention_days` like the digests: the retention pattern is extended to
`YYYY-MM-DD-review.md`.

## 4. The two modes

### 4.1 Unattended: the weekly routine

- A second cloud routine, separate from the nightly one, with its own prompt
  (`templates/routine/review-prompt.md`) and schedule. It needs the Atlassian connector (Jira) and `gh`
  only as far as `PB routine finish` does.
- Same lane as the nightly routine: `PB routine start --branch docs/brain`, work, `PB validate`,
  `PB routine finish --skill review`, into the one PR "Brain updates". Same failure handling
  (`discard`, `conflict`, `rejected`). It follows `brain/.pb/toolkit/skills/review/SKILL.md`: `review` joins
  the vendored routine skills.
- Scheduled away from the nightly run (default: Sunday 04:00, `0 4 * * 0`) **(call)**. If both push at the
  same time, the existing `conflict` handling applies: nothing is pushed, the next run redoes the work.
- Configuration in `brain/.pb/schema/sources.md`: `review: {schedule: "<cron>", trigger_id: <id>}`, checked
  by the same schedule validation. `/pb:routine-setup` gains a step that offers it, renders the prompt and
  creates the routine; `/pb:routine-setup show` prints it.
- After a successful run: `PB state set review last '<YYYY-MM-DD>'`.
- Run on demand: `/pb:review --auto` runs the unattended half locally, in a temporary worktree of
  `docs/brain`, as `/pb:sync` does when typed by the user. `/pb:routine-run review` starts the cloud
  routine now **(call)**.

### 4.2 Interactive: the owner

`/pb:review [scope] [--check] [--full]`, where `scope` is a feature, a process, a Jira key or nothing
(everything).

1. **Where it runs (decided by the owner).** In the working branch, like every other interactive skill:
   changes are uncommitted files of that branch, saved with `PB save`, and reach the default branch with
   the branch's own PR. Nothing is pushed by the skill, so nothing the person answered can be lost to a
   moving `docs/brain`. The queue it sees is the one of the branch: what the routine queued arrives with
   `/pb:merge`. When `origin/docs/brain` is ahead of the default branch, say so in one line ("the routine
   has newer changes waiting: run `/pb:merge` first to review them too") and go on. A developer may run it
   on their own branch, as they ran `/pb:lint`. `--check` reports what the review would change and ask,
   and writes nothing **(call)**.
2. **One question:** functional competence, technical, or both (`AskUserQuestion`).
3. **Unattended half first, when it is not fresh:** if the review last ran more than 7 days ago (as
   `origin/docs/brain` records it, else the branch), or never, or `--full` is given, run 3.2 first;
   otherwise go straight to the queue **(call)**.
4. **The queue, one item at a time**, in the user's language, only items whose area is one the user
   declared or `any`: first `pending.md` lines, then open questions, oldest first. For each: what the doubt
   is, both versions with their sources, up to two candidate answers drawn from the brain, its sources and
   the code, the recommended one first. Options always include "still open, I don't know" and, for open
   questions, "no longer relevant"; for `pending.md` lines, "leave it as it is" (remembered, see 3.3);
   the free answer is always possible. Rules of today's `/pb:questions`
   hold unchanged: never two questions in one call, never answer for the user, an answer that contradicts an
   accepted decision is not written as given.
5. **Apply each answer:** as today's `/pb:questions` step 3 for open questions (a `decision` when it
   constrains future work, otherwise the canonical page; the open-question page is deleted and its links
   replaced); for `pending.md` lines, the chosen action (merge as today's `/pb:lint --fix` describes,
   delete, move, create the concept), then the line is removed. "Still open" leaves the item.
6. **Close:** the closing flow of `writing.md` (`PB validate`, `PB save` with every file created, changed
   or deleted, `pending.md` and the report of 3.4 included; commit only if asked). Summary to the user:
   answered, left open, left for the other competence (count), the watched points.

The user can stop at any item; what was answered is kept. Before the close they can ask to revert a change
of this session by its number in the report; a reverted unattended-half change is remembered as a ticked
line (3.3).

The state key `review last` is written only by unattended runs on `docs/brain`, like the sync cursors; the
interactive mode reads it as the branch has it.

## 5. What changes in the plugin

- **New:** `skills/review/SKILL.md`; `templates/routine/review-prompt.md`; `brain/.pb/pending.md` (created
  on first use); `review` in `sources.md` (preset prose and validation); `review` in the vendored routine
  skills; a `review` state key.
- **Removed:** `skills/lint/`, `skills/questions/`. `PB lint` (the toolkit command) stays: the review starts
  from its findings.
- **Updated:** `/pb:routine-setup` (review step, `show`), `/pb:routine-run` (`review`), `conventions.md`
  (skill list, modes), `writing.md` (pointer to the review's rules where they extend the writing rules),
  the `open-question` type prose (its mention of `/pb:questions`), `README.md`,
  `tests/test_plugin_layout.py`, plugin version 0.7.0.
- **Toolkit:** `review` accepted as a state source; schedule validation for `review.schedule`; `review` in
  the vendored skills; retention pattern; `pending.md` parsing, validation and the PR-description line;
  `superseded-referenced` no longer fires on a successor decision that links the one it supersedes (rule 9
  forbids editing it, so the finding would come back every week).
- Existing brains: `PB toolkit-sync` and save, as after any upgrade; `upgrade` also patches the
  `/pb:questions` mention in their copy of the `open-question` prose. No page format changes.

## 6. Left to the builder

- How the unattended half reads the whole brain within context limits. Constraint: when subagents are
  available, page bulk stays out of the main session, as in `/pb:sync` — reviewers read clusters of pages
  (for instance a feature's context pack and the pages it links, plus the glossary) and return findings;
  the main session applies them. Cross-cluster duplicates must still be found (the glossary and the
  folders' generated `README.md` files are the cheap map).
- The exact wording of the routine prompt and of the skill, the tests, and the order of the work.
- Whether `PB lint` gains new deterministic checks that would make rule 6 cheaper (e.g. an alias used as
  plain text where the title should be).
