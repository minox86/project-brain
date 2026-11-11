---
name: capture
description: Analyses the current working session and feeds the project brain with the durable knowledge it produced — decisions taken and alternatives discarded, how modules and interfaces really behave, domain concepts, open questions — with a preview before writing. Use when a developer asks to capture, save or distil this session or conversation into the brain, typically at the end of a task.
argument-hint: "[focus, optional]"
---

# /pb:capture — distil the current session

Arguments: `$ARGUMENTS` (an optional focus, e.g. "only the retry decision")

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only (Claude Code).

## 1. Re-read the session

Go through the current conversation from the start: what was asked, what was explored, what was decided, what was changed. Collect the files touched or discussed (`git diff --name-only` against the merge base plus files read in the session) and map them to the brain with `PB context --paths <files…>`: those pages are the first candidates to update.

## 2. Extract durable knowledge

Keep only items that pass the **significance gate**:
- **decisions** taken in the session, with the alternatives considered and why they were discarded;
- **discoveries** about how modules and interfaces actually behave (invariants, gotchas, implicit contracts) that the code does not make obvious;
- **domain concepts** introduced or clarified;
- **open questions** left unresolved;
- **epic context**: when the branch name or the session names an active epic, constraints and scope clarifications that matter only until it ships go on its `epic` page;
- **wrong brain content** discovered during the session → handle it with the `/pb:fix` flow (step 4 of that skill onwards), in the same run.

Discard: debugging steps, dead ends without a lesson, anything the diff already shows, task status, temporary workarounds that will not survive the PR.

## 3. Preview

For each item show: target page · create/update · the exact lines added or changed. Ask: "Write all / choose by number / none".

## 4. Write and close

Write, then the closing flow: `PB save <files written>`. The pages stay in this branch and reach the default branch with its PR, next to the code they describe.
