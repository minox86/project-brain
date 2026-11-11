# project-brain — Git interaction redesign (0.5)

Status: draft for approval · 2026-11-11 · supersedes the "Modes", "Write flow" and "CI" parts of
`2026-10-31-project-brain-design.md` and the saving model of 0.2–0.4.

Lines marked **(call)** are choices made while writing this document, not decisions of the product owner:
check them while reading.

## 1. Intent

The plugin has no users yet. Before it gets any, the way the brain moves through git is redesigned around
two kinds of people:

- **Tech people** work in Claude Code. They own their working branch and its release cycle, and want the
  brain to be fed *in that branch*, travelling to the default branch with the code that motivated it.
- **Non-tech people** work in Claude Cowork. For now they only *read* the brain, from the default branch,
  and must never meet git.

Up to 0.4 every save, from anyone, went to a dedicated branch `docs/brain` through a hidden copy of the
brain, and reached the default branch with a "brain PR". That kept git away from everybody, at the cost of
a brain that lived apart from the code, a second PR to merge, and a large amount of machinery (managed
worktree, lock, parked drafts, offline queue, review branches, a merge-back workflow). With non-tech
writing out of scope, that cost buys nothing.

## 2. Goals, non-goals, anti-goals

**Goals**

- The default branch is the single source of truth of the brain. Everything read by people who are not in
  a working branch (Cowork, a fresh clone, an agent on the default branch) comes from there.
- A developer's brain changes are ordinary changes of their working branch: same commits, same PR, same
  review, same merge as the code.
- The routine is the only writer that is not a developer. It has one fixed branch, `docs/brain`, and one
  PR towards the default branch.
- Much less code than 0.4.

**Non-goals**

- Writing from Cowork. Non-tech knowledge keeps entering through Confluence and Teams, ingested by the
  routine. (A later phase may add a write lane; this design should not make it harder, but does not
  prepare it.)
- Non-developers writing through Claude Code desktop. `/pb:setup` no longer targets them.
- Automatic merge to the default branch, and any bot that pushes to the default branch.
- A migration path from 0.4 beyond what section 9 lists: there are no installations to migrate.

**Anti-goals**

- pb committing, pushing, rebasing or switching branch in a developer's checkout. The branch is theirs.
- A brain PR that a human must remember to merge for *developer* knowledge to reach the default branch.
- Non-tech people being told to look at a branch, a PR or a diff.

## 3. Branch model

| Branch | Who writes brain pages there | How they reach the default branch |
|---|---|---|
| a working branch | the developer who owns it, through the pb skills in Claude Code | the code PR, with the team's normal flow |
| `docs/brain` | the routine only | one PR "Brain updates" that the routine keeps open and a developer merges |
| the default branch | nobody directly | — |

`pb/review/<timestamp>` branches no longer exist.

## 4. Developers (repo mode)

Decided by the product owner: pages are written in the working branch; generated files are committed in
the working branch too.

- **Where pb reads and writes.** `brain/` in the working tree of the current checkout, whatever branch it
  is on. There is no managed copy. What the developer reads is the brain as of their branch (the default
  branch at the last merge or rebase, plus their own pages).
- **Saving.** The closing step of `capture`, `put`, `fix`, `meeting`, `lint --fix`, `schema`
  becomes: validate the pages written, regenerate the generated files (index, glossary, feature catalogue,
  context packs, backlinks), and report what changed. `PB save` keeps its name and its `PATH…` argument
  but does only that.
- **pb does not commit (call).** The changed files are left in the working tree, like any file Claude
  edits; the developer commits them with the code, or asks Claude to. `PB commit` stays available for the
  routine and for a developer who asks. Nothing is pushed by pb.
- **On the default branch.** pb writes anyway and says once that the pages will need a branch and a PR
  like any other change. No refusal.
- **No brain in the working tree** (a branch cut before the brain arrived): pb says to bring the default
  branch into the branch; it does not do it.
- **Watched points.** At save time pb still evaluates `brain/schema/review.md` and tells the developer
  which changes touch a watched point and who the area reviewers are. Nothing is held back locally.
- **Concurrency.** The lock goes away: two sessions in one checkout share a working tree, as with code.
- **Removed.** The managed worktree, `PB workspace sync`, the lock, parking of other sessions' drafts, the
  pending/held state, `save --continue`, the offline queue, review branches and `ensure_promotion` from
  the developer path.

### Generated files and conflicts

Two PRs that both touch the brain will often conflict on generated files. Accepted by the product owner;
pb makes it cheap:

- `PB generate` is safe to run by hand at any time and is what resolves such a conflict: take either side
  of the generated files, run it, commit. Conflicts on pages in a working branch are the developer's, like
  any conflict in their branch.
- `brain/.gitattributes` marks generated files `linguist-generated`, so GitHub collapses them in PR diffs
  (**call**).
- CI checks freshness (section 7), so a stale index never survives a PR.
- **Generation no longer depends on today's date (call).** Today `generate` drops old closed decisions,
  questions and epics from the index by age and deletes old digests, so the same pages give different
  output on different days and a failing freshness check could not be trusted. Instead: the routine, and
  only the routine, marks such pages `archived: true` in their frontmatter and deletes old digests;
  `generate` reads the flag and never deletes anything that is not a generated file.

### Ingestion from the sources stays in the routine lane (call)

`/pb:sync` and `/pb:routine-run --local` read shared cursors (`brain/.pb/state/`). If a developer's branch
moved them, the routine would not see it until that PR merged and would ingest the same content twice. So
both keep running as a routine run: in a temporary worktree on `docs/brain`, pushed there, never in the
developer's checkout. They are the one place where pb pushes on a developer's behalf, and only to
`docs/brain`. Cursors and state files therefore change only on `docs/brain`. The skills that write into
the working branch are `capture`, `put`, `fix`, `meeting`, `lint --fix` and `schema`.

## 5. Routine

Decided by the product owner: the routine keeps `docs/brain` as its fixed branch and opens a PR towards
the default branch.

- **No automatic merge, anywhere** (decided by the product owner). Neither the routine nor a workflow
  merges the default branch into `docs/brain`, and nothing merges `docs/brain` into the default branch.
  Bringing the two together is started by whoever maintains the repo, by running `/pb:merge` (section 5b).
- **Start.** Check out `docs/brain` (created from the default branch if missing). If `docs/brain` is behind
  the default branch, the run goes on with what it has and says so in the digest and in the PR
  description: "`docs/brain` is behind `<default>`: run `/pb:merge` to bring these changes to `<default>`".
  One exception that is not a merge (**call**): when `docs/brain` holds nothing the default branch lacks
  (its last PR was merged), the routine restarts the branch from the default branch, so each cycle begins
  with every page developers merged and "update before create" works.
- **Finish.** Validate, regenerate, commit, push to `docs/brain`, then find or open the PR
  `docs/brain` → default branch.
- **Review.** No separate review PR. Everything the routine wrote is already waiting for a human in that
  PR; its description lists the changes on watched points and low-confidence items, and the area
  reviewers are requested on it (**call**).
- The routine never touches a working branch and never pushes to the default branch.

## 5b. `/pb:merge`: bringing the routine's changes to the default branch

Decided by the product owner: nothing merges on its own schedule. `/pb:merge` (**call**: the name) has one
purpose: carry what the routine wrote on `docs/brain` into the default branch, resolving conflicts and
inconsistencies on the way; in the same pass it brings the default branch into `docs/brain`. It is not a
tool for a developer's working branch. Whoever maintains the repo runs it, in Claude Code, when they want
the routine's knowledge on the default branch. Running it is the request: it carries the merge through by
itself and does not ask for confirmation of each step.

It works in a temporary worktree on `docs/brain`, so the person's checkout and branch are not touched
(**call**).

1. **Default branch into `docs/brain`.** A real git merge, so "Brain updates" stops conflicting.
2. **Only the brain is merged.** Conflicts under `brain/` are resolved by the skill:
   - **generated files**: never merged by hand; regenerated once the pages are settled;
   - **pages**: both versions are combined following the type's writing rules;
   - **state files** (`brain/.pb/state/`): `docs/brain` wins, they change only there;
   - **schema and toolkit**: the one kind of brain conflict it never settles alone: it asks.
3. **Anything else raises an alert.** `docs/brain` must differ from the default branch only under
   `brain/`. If it carries other changes, or the merge conflicts outside `brain/`, the skill stops before
   pushing anything and lists those files: they have to be moved to a code PR by a person.
4. **Inconsistencies.** A merge that git considers clean can still leave the brain contradicting itself,
   so the skill compares what the routine wrote with what developers merged meanwhile, not only the
   conflicted files, and looks for:
   - the same concept, feature or decision created as two different pages, one per side;
   - a page one side changed and the other deleted, renamed or superseded;
   - statements that disagree: a glossary term defined two ways, a feature status, a decision accepted on
     one side and contradicted or superseded on the other, an interface contract described differently;
   - links to pages the other side removed or renamed.
   What the sources or the dates settle, it fixes and reports. What they do not settle, it **asks the
   person**, one question per inconsistency, with both versions and where each came from. If the person
   does not know, the disagreement becomes an `open-question` page, as everywhere else in pb.
5. **Validate, commit, push to `docs/brain`.** The same checks as a save, freshness included.
6. **`docs/brain` into the default branch.** Through the "Brain updates" PR, never with a direct push
   (**call**): the skill waits for the PR's checks and merges it. If the repository's rules ask for
   something the skill cannot give (an approval, a failing required check), it stops there and says
   exactly what is missing and from whom; run again afterwards, it only has to merge.
7. **Report.** Pages combined (with what was kept from each side), inconsistencies fixed, questions asked,
   open questions created, and whether the default branch now has the changes.

Behind it, deterministic CLI helpers (how the two branches differ, the brain conflicts by kind, the pages
each side changed, "resolve generated files", find/merge the PR) so the skill does not improvise git;
their shape is left to the builder. The routine's "behind" notice names `/pb:merge`.

## 6. Non-tech people (read mode)

- In Cowork, `/pb:ask` and `/pb:context` read `brain/` from the **default branch** through the GitHub
  connector. No branch has to be selected.
- No write commands. The tip in the README stays: write on Confluence or in the Teams channel, mention the
  Jira epic key, and the routine files it.
- What they see lags behind a developer's branch until its PR is merged, and behind the routine until
  "Brain updates" is merged. That is the intended meaning of "the default branch is the truth".

## 7. CI

- `pb-validate` runs on every pull request, as today, and passes when no brain page changed. The trigger
  on pushes to `docs/brain` is dropped.
- New in `validate`: a **freshness** check. On the PR's merge result, regenerate and fail if the generated
  files differ, with the message "run `PB generate` and commit" (**call**: failing rather than warning).
- New job **`review`** (**call**): on a PR that changes brain pages, evaluate `review.md` against the base
  and, when watched points or `brain/schema/` or `brain/.pb/toolkit/` are touched, write them in the job
  summary and request the area reviewers. It informs; it does not block. Blocking stays with the repo's
  own branch protection.
- `brain-only` stays for PRs whose head is `docs/brain`.
- `pb-brain-branch` is removed.

## 8. Init, setup, docs

- **`/pb:init`** still works in a temporary copy so the checkout is untouched, but creates a branch
  `pb/init` from the default branch and opens an ordinary PR with `brain/`, the workflow, the `CLAUDE.md`
  pointer and `.claude/settings.json`. The GitHub checks about `docs/brain` protection move to
  `/pb:routine-setup`, the only place that needs them.
- **`/pb:setup`** prepares a developer's computer; the wording about saving without git and the workspace
  step are removed.
- **`references/conventions.md`, `references/writing.md`, every skill's closing flow,
  `templates/routine/prompt.md`, `templates/brain/AGENTS.md`, README, plugin description**: rewritten for
  this model.
- Version **0.5.0**.

## 9. Upgrading from 0.4

One paragraph in the README: merge the open brain PR, update the plugin, run `/pb:init` (it removes
`pb-brain-branch`, updates `pb-validate` and the vendored toolkit through a normal PR), run
`/pb:routine-setup` again.

## 10. Risks and spikes

| # | Question | If it fails |
|---|---|---|
| S1 | Cowork's GitHub connector reads `brain/` on the default branch of a large monorepo | unchanged fallback: Confluence mirror |
| S2 | The cloud routine can push to `docs/brain` and open the PR to the default branch | unchanged |
| S6′ | The routine can restart `docs/brain` from the default branch (a non-fast-forward push) when the default branch changed workflow files | the routine leaves the branch as it is and reports "behind"; the maintainer realigns it with `/pb:merge` |
| S7 | A workflow can request reviewers on a PR with the default token | the `review` job only writes the summary and a PR comment |

Known and accepted: generated-file conflicts between parallel PRs; "Brain updates" conflicts with the
default branch as soon as a code PR carrying pages is merged, and while it conflicts GitHub runs no checks
on it, so merging it takes a `/pb:merge` pass by the maintainer; a correction made to that PR on GitHub's
web editor leaves the generated files stale until someone runs `/pb:merge` or `PB generate` on the branch;
a routine PR left unmerged makes Cowork's view of Teams/Confluence knowledge stale.

## 11. Left to the builder

- How much of `workspace.py` survives versus moving the remaining helpers (`default_branch`, `origin_repo`,
  PR creation) elsewhere.
- The exact output of `PB save` and the wording of messages.
- Test layout: delete the tests of removed behaviour, cover the new save, routine start/finish, freshness
  and review jobs.
