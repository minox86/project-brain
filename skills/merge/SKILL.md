---
name: merge
description: Brings what the routine wrote on `docs/brain` to the default branch: merges the default branch into `docs/brain`, resolves brain conflicts and inconsistencies, asks when sources do not settle one, and merges the Brain updates PR. Use when the user asks to merge, land or publish the brain updates or the routine's changes, or when `docs/brain` is behind or in conflict.
---

# /pb:merge — bring the routine's changes to the default branch

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only, run by whoever maintains the repo.

The routine is the only writer on `docs/brain` and keeps one PR, "Brain updates", from `docs/brain` to the default branch. This skill carries those changes to the default branch, bringing the default branch into `docs/brain` on the way. It is not a tool for a developer's working branch.

Running it is the request: carry the merge through without asking to confirm any step. Ask only the questions below (schema conflicts, inconsistencies the sources do not settle). Everything happens in a temporary worktree on `docs/brain`: never touch the user's checkout, branch or uncommitted files, and never push to the default branch. It is reached only by merging the PR. Never improvise git where a `PB merge` command does the work.

## 1. Default branch into `docs/brain`

`PB merge start --worktree <tmp dir outside the repo>`. It fetches, then merges the default branch into `docs/brain` in that worktree without committing. The result gives `worktree`, `brain`, `base` (the commit both sides start from), `behind` and `ahead`, the brain conflicts by kind in `conflicts`, and the brain pages each side changed since `base` in `changed.routine` (what the routine wrote) and `changed.default` (what developers merged).

On `"alert": "outside-brain"` stop: nothing was merged or pushed and there is no worktree to clean. `docs/brain` must differ from the default branch only under `brain/`. List the `files`, say that a person has to move them to a code PR, and that `/pb:merge` can run once they are gone.

## 2. Brain conflicts

- `conflicts.generated`: leave them alone. The next step regenerates them once the pages are settled.
- `conflicts.state`: already resolved by `PB merge start`: `docs/brain`'s cursors, the union of both sides' suppressions. Nothing to do.
- `conflicts.pages`: combine both versions into one page that follows the type's writing rules in `references/writing.md` and `brain/schema/types/<type>.md`. Keep every fact from both sides, drop duplicates, and remove the conflict markers. When the two sides disagree, the source or the date settles it as in step 3; otherwise ask about it there. Write the page in the worktree, then `git -C <worktree> add <path>`. Note what you kept from each side for the report.
- `conflicts.schema` (`brain/schema/`, `brain/.pb/toolkit/`): the one kind you never settle alone. Ask the person, one question per file, showing both versions (`git -C <worktree> show :2:<path>` is the `docs/brain` side, `:3:<path>` the default branch side). Write what they choose, then `git -C <worktree> add <path>`.

## 3. Inconsistencies

A merge that git considers clean can still leave the brain contradicting itself, so compare what each side wrote, not only the conflicted files. Read `git -C <worktree> diff <base> origin/docs/brain -- <changed.routine paths>` and `git -C <worktree> diff <base> origin/<default> -- <changed.default paths>`, then the merged pages in the worktree, and look for:

- the same concept, feature or decision created as two different pages, one per side (`PB --brain <brain> resolve "<name>"` helps);
- a page one side changed and the other deleted, renamed or superseded;
- statements that disagree: a glossary term defined two ways, a feature status, a decision accepted on one side and contradicted or superseded on the other, an interface contract described differently;
- links to pages the other side removed or renamed.

What the sources or the dates settle, fix in the worktree and note for the report: merge duplicate pages into one and fix the links to it, follow a supersession, keep the newer source on a contradiction. What they do not settle, ask the person, one question per inconsistency, with both versions and where each came from (the `sources` of each page, the commit on each side). If they do not know, record the disagreement as an `open-question` page citing both sources and link it from the affected pages, as everywhere else in pb.

## 4. Validate, commit, push `docs/brain`

`PB merge finish --worktree <worktree> -m "pb(merge): bring <default> into docs/brain"`. It regenerates the generated files, runs the same checks as a save on every page either side changed and on the ones you resolved, commits the merge and pushes `docs/brain`.

- `unresolved`: paths still in conflict. Settle them (step 2) and run it again.
- `errors`: fix each page in the worktree, `git -C <worktree> add` it, and run it again.
- `"pushed": false` with a problem: `docs/brain` moved on origin meanwhile (a routine run). Clean up (step 6) and start `/pb:merge` again.

## 5. `docs/brain` into the default branch

`PB merge land`. It finds the Brain updates PR (or opens it), waits for its checks and merges it through the GitHub API.

- `"merged": true`: the default branch has the changes.
- `missing`: the repository asks for something you cannot give (an approval, a failing or still-running check). Say exactly what is missing and from whom, give the PR link from `pr`, and say that running `/pb:merge` again once it is there finishes the job: it only has to merge.
- `problems`: report them as they are.

## 6. Clean up and report

Always finish with `PB routine cleanup --worktree <worktree>`, also when you stopped early after step 1 created the worktree.

Report:
- pages combined, with what was kept from each side;
- inconsistencies fixed, and what settled each;
- questions asked, and the answers;
- open questions created;
- whether the default branch now has the changes, or what is still missing and from whom.
