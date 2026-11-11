# Git Interaction Redesign (0.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Developers feed the brain in their working branch, the routine alone writes on `docs/brain`, and `/pb:merge` carries the routine's changes to the default branch.

**Architecture:** The managed brain copy (`workspace.py`) is deleted: `PB save` validates and regenerates in the working tree and never commits. The routine keeps one branch and one PR; a new `merge.py` gives `/pb:merge` deterministic helpers (start, finish, land). Generation becomes date-independent so CI can check freshness.

**Tech Stack:** Python 3.9+ standard library only, `git` ≥ 2.38 (for `git merge-tree --write-tree`), `gh api` (REST only: cloud routines cannot use `gh pr`), GitHub Actions, `unittest`.

**Spec:** `docs/specs/2026-11-11-git-interaction-redesign.md`

## Global Constraints

- pb never commits, pushes, rebases or switches branch in a developer's checkout. `PB commit` runs only when asked.
- pb pushes only to `docs/brain`, and only from the routine, `/pb:sync`, `/pb:routine-run --local` and `/pb:merge`, each in a temporary worktree.
- Nothing merges on a schedule: no workflow and no routine step merges branches. Nothing pushes to the default branch; it is reached only by merging a PR.
- `pb/review/<timestamp>` branches and the `pb-brain-branch` workflow no longer exist.
- `generate` takes no date and deletes only generated files.
- The brain PR is titled `Brain updates`, head `docs/brain`, base the default branch.
- No `bin/` directory; skills call `python3 <plugin>/scripts/pb.py`.
- Every command prints one JSON object and exits 0 (ok), 1 (findings/errors/conflict/alert) or 2 (usage/internal).
- Tests: `cd tests && python3 -m unittest -q` (206 pass before this plan; no pytest).
- Version `0.5.0`.

## Review Focus

1. `PB save` in a checkout with a merge or rebase in progress: it must still validate and regenerate, never fail on git state. (Task 2)
2. `PB save` when a page was deleted and another page still links it: error `broken-link`, nothing regenerated. (Task 2)
3. Routine restart when `docs/brain` was squash-merged and the default branch moved on: must be detected as "holds nothing the default branch lacks". (Task 3)
4. `pb merge start` when `docs/brain` carries a file outside `brain/`: alert, exit 1, the remote branch untouched and no worktree left with a half merge. (Task 4)
5. `pb merge land` when the PR needs an approval: `merged: false` with `missing` naming it; a second call after approval merges. (Task 4)

## File Structure

| File | Responsibility after this plan |
|---|---|
| `scripts/pb_core/repo.py` (new, from `workspace.py`) | git and GitHub helpers: `git`, `default_branch`, `origin_repo`, `repo_root`, `gh_repo`, `gh_json`, `ensure_brain_pr`, `request_reviewers` |
| `scripts/pb_core/save.py` (new) | `save()`: validate, regenerate, report watched points |
| `scripts/pb_core/retention.py` (new) | `apply_retention()`: mark old closed pages `archived: true`, delete old digests |
| `scripts/pb_core/merge.py` (new) | `merge_start`, `merge_finish`, `merge_land` |
| `scripts/pb_core/workspace.py` | deleted |
| `scripts/pb_core/gitops.py` | `commit`, routine start/finish/discard/cleanup, without review branches |
| `scripts/pb_core/generate.py`, `lint.py`, `brain.py`, `validate.py`, `cli.py`, `scaffold.py` | modified |
| `templates/github/pb-validate.yml` | freshness step, `review` job; `pb-brain-branch.yml` deleted |
| `skills/merge/SKILL.md` (new) | the `/pb:merge` flow |
| `references/`, other `skills/`, `templates/routine/prompt.md`, `templates/brain/AGENTS.md`, `README.md`, `docs/spikes.md` | rewritten for the model |

---

### Task 1: Date-independent generation and retention

**Files:**
- Modify: `scripts/pb_core/generate.py`, `scripts/pb_core/lint.py`, `scripts/pb_core/validate.py`, `scripts/pb_core/cli.py`
- Create: `scripts/pb_core/retention.py`
- Test: `tests/test_generate.py`, `tests/test_lint.py`, `tests/test_retention.py` (new)

**Interfaces:**
- Produces: `generate(brain) -> {"written": [rel], "deleted": [rel]}` (no `today`; `deleted` only ever holds `context/*.md`).
- Produces: `is_archived(page) -> bool`: true only when the frontmatter has `archived: true`.
- Produces: `apply_retention(brain, today: datetime.date) -> {"archived": [rel], "deleted": [rel]}`.
- Produces: CLI `pb retention [--today YYYY-MM-DD]`; `pb generate` loses `--today`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_retention.py
def test_old_closed_decision_is_flagged_and_leaves_index(self):
    # decision, status: superseded, updated: 2026-01-01; archive_after_days default 90
    result = apply_retention(brain, datetime.date(2026, 11, 11))
    self.assertEqual(result["archived"], ["decisions/Old.md"])
    self.assertIn("archived: true", (root / "decisions/Old.md").read_text())
    generate(brain_reloaded)
    self.assertNotIn("[[Old]]", (root / "index.md").read_text())
    self.assertIn("Archived: 1 pages (not listed).", (root / "index.md").read_text())

def test_recent_or_open_pages_are_not_flagged(self): ...        # archived == []
def test_retention_is_idempotent(self): ...                     # second call: archived == [], file unchanged
def test_old_digest_deleted_by_retention_not_by_generate(self):
    # digests/2026-01-01.md
    generate(brain); self.assertTrue(digest.exists())
    self.assertEqual(apply_retention(brain, datetime.date(2026, 11, 11))["deleted"], ["digests/2026-01-01.md"])

# tests/test_generate.py
def test_generate_is_the_same_on_any_day(self):
    # an old superseded decision WITHOUT archived: true stays in index.md
    generate(brain); self.assertIn("[[Old]]", index_text)
def test_archived_flag_passes_validate(self): ...               # no error for the key `archived`
```

- [ ] **Step 2: Run them, expect failures** (`cd tests && python3 -m unittest test_retention test_generate -q`: `ModuleNotFoundError: pb_core.retention`, `TypeError` on `generate(brain)`).

- [ ] **Step 3: Implement**

- `generate(brain)`: drop the `today` parameter and the whole digest block; `_index` calls `is_archived(p)`.
- `retention.py`: a page qualifies when its status is in `CLOSED[type]`, `updated` is more than `archive_after_days` (default 90) before `today`, and it is not already flagged. `frontmatter.py` has no writer: insert the line `archived: true` immediately before the closing `---` of the frontmatter, touching nothing else. Digests: move the deleted block from `generate`, `digest_retention_days` default 30.
- `validate.py`: accept `archived` (boolean) on every type.
- `lint.py`: `is_archived(p)`. `cli.py`: `_cmd_generate` without `_today`; new `retention` subcommand.
- Update the existing callers in tests that pass `today` to `generate`.

- [ ] **Step 4: Run the whole suite, expect OK.**
- [ ] **Step 5: Commit** `feat(generate): date-independent generation; retention moves to its own command`

---

### Task 2: Save in the working tree; remove the managed copy

**Files:**
- Create: `scripts/pb_core/repo.py`, `scripts/pb_core/save.py`
- Delete: `scripts/pb_core/workspace.py`, `tests/test_workspace.py`
- Modify: `scripts/pb_core/brain.py` (remove `_managed_copy` and its call), `scripts/pb_core/cli.py`, `scripts/pb_core/gitops.py` (imports only; behaviour changes in Task 3)
- Test: `tests/test_save.py` (new), `tests/test_brain.py`, `tests/test_cli.py`

**Interfaces:**
- Produces in `repo.py`: `git(cwd, *args, check=True, env=None)`, `default_branch(repo) -> str`, `origin_repo(repo) -> str | None`, `repo_root(start) -> Path`, `gh_json(args) -> dict | list | None`, `gh_repo(brain) -> str | None` (`github.repo` of `brain.sources`, else `origin_repo`). Moved unchanged from `workspace.py` except `gh_repo`, which now takes a `Brain`.
- Produces: `save(repo: Path, paths=()) -> dict` with keys `saved: bool`, `errors: [{"path","code","message"}]`, `files: [repo-relative paths changed, generated included]`, `watched: [{"path","reason"}]`, `reviewers: {"users": [], "teams": []}`, `markdown: str`, `branch: str`, `on_default: bool`.
- Produces: CLI `pb save [PATH…]` (exit 1 when `errors`). `-m`, `--continue`, `--force-review` and the `workspace` command are removed.
- No brain in the checkout: `UsageError` with payload `{"code": "no-brain", "error": "no brain/ in this checkout: bring the default branch into your branch, or create the brain with /pb:init"}`.

- [ ] **Step 1: Write the failing tests** (`tests/test_save.py`, on `GitRepoCase` from `test_gitops.py`, working on branch `feat/x`)

```python
def test_save_validates_regenerates_and_does_not_commit(self):
    head = git(self.repo, "rev-parse", "HEAD")
    write(page("feature", "Approvals"))
    code, out, _ = run_cli("save", "brain/functional/features/Approvals.md", cwd=self.repo)
    self.assertEqual(code, 0); self.assertTrue(out["saved"])
    self.assertIn("brain/index.md", out["files"])
    self.assertIn("brain/functional/features/Approvals.md", out["files"])
    self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)          # nothing committed
    self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/x")
    self.assertFalse(out["on_default"])

def test_save_without_paths_takes_every_changed_brain_file(self): ...
def test_invalid_page_blocks_and_regenerates_nothing(self): ...          # code 1, errors, index.md unchanged
def test_secret_in_page_blocks(self): ...                                # errors[0]["code"] == "secret"
def test_deleted_page_still_linked_blocks(self): ...                     # code "broken-link"   (Review Focus 2)
def test_watched_point_is_reported_not_held(self):                       # review_policy = True
    # a decision set to accepted
    self.assertTrue(out["saved"]); self.assertEqual(out["watched"][0]["path"], "decisions/X.md")
    self.assertTrue(out["reviewers"]["users"] or out["reviewers"]["teams"])
def test_save_on_default_branch_is_allowed_and_flagged(self): ...        # saved True, on_default True
def test_save_during_merge_in_progress(self): ...                        # MERGE_HEAD present: saved True (Review Focus 1)
def test_no_brain_in_checkout(self): ...                                 # exit 2, payload code "no-brain"
def test_find_brain_ignores_a_leftover_managed_copy(self):               # tests/test_brain.py
    # <git-dir>/pb/brain-worktree/brain exists: find_brain still returns <repo>/brain
```

- [ ] **Step 2: Run, expect failures** (`No module named pb_core.save`).

- [ ] **Step 3: Implement**

- `save()`: scope = the given paths, else every file under `brain/` that differs from `HEAD` or is untracked, minus `GENERATED`. Errors come from the checks of today's `workspace._check` (secrets in touched files, `validate` of touched pages against `HEAD`, links left pointing at a page this save deletes): move that function into `save.py`. On errors return without generating. Otherwise `generate(brain)`, then `review(brain, "HEAD", noise_holds=False)` for `watched`, `reviewers`, `markdown`; add every scoped path under `brain/schema/` or `brain/.pb/toolkit/` to `watched` with reason `configuration or toolkit change: always reviewed`.
- `files` = `git status --porcelain -- brain` after generation.
- Delete `workspace.py`; `cli.py` and `gitops.py` import from `repo.py`. Leave `gitops.routine_finish` compiling by importing `ensure_brain_pr`/`request_reviewers` stubs only if needed: Task 3 rewrites it, so in this task remove its calls to `_open_review` and `ensure_promotion` and drop the tests of those in `tests/test_gitops.py`, `tests/test_review.py`, `tests/test_review_fixes.py`, `tests/test_deep_review.py` that exercise review branches or the managed copy (keep every test of `review()` itself).

- [ ] **Step 4: Run the whole suite, expect OK.** `grep -rn "workspace" scripts/` returns nothing.
- [ ] **Step 5: Commit** `feat(save): pages are saved in the working branch; the managed brain copy is gone`

---

### Task 3: Routine on `docs/brain` with one PR

**Files:**
- Modify: `scripts/pb_core/gitops.py`, `scripts/pb_core/repo.py`, `scripts/pb_core/cli.py`
- Test: `tests/test_gitops.py`, `tests/test_routine_options.py`, `tests/test_brain_pr.py` (new)

**Interfaces:**
- Consumes: `apply_retention`, `generate(brain)`, `repo.*`.
- Produces: `adds_nothing(repo, branch, base) -> bool`: true when merging `origin/<branch>` into `origin/<base>` would leave `<base>`'s tree unchanged (`git merge-tree --write-tree`; false when the command fails or conflicts).
- Produces: `routine_start(repo, branch, worktree=None) -> {"branch", "created": bool, "restarted": bool, "behind": int, ["worktree", "brain"]}`.
- Produces: `routine_finish(brain, branch, message, confidence=()) -> {"committed": bool, "pushed": bool, "conflict": bool, "pr": url | None, "watched": [...], "reviewers": {...}, "behind": int, "retention": {...}, "problems": [str]}`. The keys `review` and `promotion` are gone.
- Produces in `repo.py`: `ensure_brain_pr(owner, base, body) -> (url | None, number | None, problem | None)` (finds the open PR `docs/brain` → `base` or opens it; when found, PATCHes its body), `request_reviewers(owner, number, reviewers) -> [problem]`, `brain_pr_body(markdown: str, behind: int, base: str) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_start_restarts_branch_when_its_pr_was_squash_merged(self):       # Review Focus 3
    # docs/brain has commit A (a page); main gets the same change as a different commit, then another commit
    out = run_cli("routine", "start", "--branch", "docs/brain", cwd=self.repo)[1]
    self.assertTrue(out["restarted"]); self.assertEqual(out["behind"], 0)
    self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "origin/main"))

def test_start_keeps_branch_with_pending_pages_and_reports_behind(self):
    # docs/brain has a page main lacks; main is 2 commits ahead
    self.assertFalse(out["restarted"]); self.assertEqual(out["behind"], 2)
    # HEAD is origin/docs/brain: nothing was merged

def test_finish_pushes_everything_in_one_branch_no_review_branch(self):   # review_policy = True, a watched page
    self.assertTrue(out["pushed"]); self.assertEqual(out["watched"][0]["path"], "decisions/X.md")
    self.assertEqual(git(self.repo, "ls-remote", "--heads", "origin", "pb/review/*"), "")
    # the watched page IS on origin/docs/brain

def test_finish_after_restart_pushes_over_the_old_branch(self): ...       # pushed True, origin/docs/brain == HEAD
def test_finish_refused_push_reports_conflict(self): ...                  # someone pushed meanwhile: conflict True, pushed False
def test_finish_runs_retention(self): ...                                 # out["retention"]["deleted"] lists an old digest

# tests/test_brain_pr.py
def test_body_names_merge_skill_when_behind(self):
    body = brain_pr_body("- decisions/X.md: decision accepted\n", 3, "main")
    self.assertIn("`docs/brain` is behind `main`: run `/pb:merge` to bring these changes to `main`", body)
    self.assertIn("decisions/X.md", body)
def test_body_without_behind_has_no_notice(self): ...
```

- [ ] **Step 2: Run, expect failures.**

- [ ] **Step 3: Implement**

- `routine_start`: after fetch, when the remote branch exists and `adds_nothing(repo, branch, default)`, check out `-B branch origin/<default>` and return `restarted: True`; otherwise check it out as today. `behind` = `git rev-list --count origin/<branch>..origin/<default>` (0 after a restart). Same logic in the worktree variant.
- `routine_finish`: `apply_retention(brain, today)`, `review()` for the watched list (nothing is excluded), `commit(..., allow_default=True)`, `generate`, commit generated files, push. Push with `--force-with-lease` only when `origin/<branch>` is not an ancestor of `HEAD` **and** `adds_nothing(repo, branch, default)`; any other non-fast-forward is `conflict: True` with no push. A refused push adds the problem `the push to docs/brain was refused` (S6′ fallback: the branch stays as it was).
- After a push to `docs/brain`: `ensure_brain_pr(owner, default, brain_pr_body(routed["markdown"], behind, default))`, then `request_reviewers`. Problems are appended, never raised.
- Delete `_open_review`, `REVIEW_PREFIX`, the held-commit logic.

- [ ] **Step 4: Run the whole suite, expect OK.**
- [ ] **Step 5: Commit** `feat(routine): one branch, one PR, reviewers on the brain PR; no automatic merge`

---

### Task 4: `pb merge` helpers and the `/pb:merge` skill

**Files:**
- Create: `scripts/pb_core/merge.py`, `skills/merge/SKILL.md`
- Modify: `scripts/pb_core/cli.py`
- Test: `tests/test_merge.py` (new), `tests/test_plugin_layout.py`

**Interfaces:**
- Consumes: `repo.*`, `generate(brain)`, the save checks of Task 2, `ensure_brain_pr`, `gitops.routine_cleanup`.
- Produces: `merge_start(repo, worktree) -> dict`:
  `{"alert": None | "outside-brain", "files": [paths outside brain/], "worktree", "brain", "base": sha, "behind": int, "ahead": int, "conflicts": {"pages": [], "schema": [], "generated": [], "state": []}, "changed": {"routine": [brain pages changed on docs/brain since base], "default": [brain pages changed on the default branch since base]}}`. Exit 1 on an alert.
- Produces: `merge_finish(repo, worktree, message) -> {"committed": bool, "pushed": bool, "errors": [...], "unresolved": [paths], "problems": [str]}`. Exit 1 when `errors` or `unresolved`.
- Produces: `merge_land(repo, wait=600) -> {"merged": bool, "pr": url | None, "missing": [str], "problems": [str]}`. Exit 1 when not merged.
- Produces: CLI `pb merge start --worktree PATH`, `pb merge finish --worktree PATH -m MSG`, `pb merge land [--wait SECONDS]`. Cleanup is `pb routine cleanup --worktree PATH`.

- [ ] **Step 1: Write the failing tests** (`tests/test_merge.py`, on `GitRepoCase`; `docs/brain` created from `main`)

```python
def test_start_reports_both_sides_and_classifies_conflicts(self):
    # docs/brain: edits features/A.md, adds decisions/R.md, regenerated
    # main: edits features/A.md differently, adds concepts/D.md, regenerated
    out = start()
    self.assertIsNone(out["alert"])
    self.assertEqual(out["conflicts"]["pages"], ["brain/functional/features/A.md"])
    self.assertIn("brain/index.md", out["conflicts"]["generated"])
    self.assertIn("brain/decisions/R.md", out["changed"]["routine"])
    self.assertIn("brain/functional/concepts/D.md", out["changed"]["default"])
    self.assertEqual(git(self.repo, "branch", "--show-current"), "main")   # the checkout is untouched

def test_state_conflict_keeps_docs_brain_side(self): ...     # brain/.pb/state/teams.json: resolved, not listed as unresolved later
def test_schema_conflict_is_listed_never_resolved(self): ... # in conflicts["schema"]; finish reports it in "unresolved"

def test_start_alerts_when_docs_brain_carries_code(self):                  # Review Focus 4
    # docs/brain also changed src/app.py
    code, out, _ = start_cli()
    self.assertEqual(code, 1); self.assertEqual(out["alert"], "outside-brain")
    self.assertEqual(out["files"], ["src/app.py"])
    self.assertEqual(remote_sha("docs/brain"), before)
    self.assertFalse(Path(worktree).exists())

def test_finish_refuses_while_pages_are_unresolved(self): ...              # unresolved == [A.md], nothing pushed
def test_finish_regenerates_validates_commits_merge_and_pushes(self):
    # after writing a resolved A.md and `git add` in the worktree
    out = finish()
    self.assertTrue(out["pushed"])
    self.assertEqual(git(self.repo, "rev-list", "--count", "origin/docs/brain..origin/main"), "0")  # main is inside docs/brain
    # index.md on origin/docs/brain lists A, R and D
def test_finish_blocks_on_invalid_resolved_page(self): ...                 # errors, pushed False

# merge_land with repo.gh_json patched (unittest.mock)
def test_land_merges_when_checks_pass(self): ...                           # merged True, PUT pulls/N/merge called with merge_method "merge"
def test_land_reports_missing_approval(self):                              # Review Focus 5
    self.assertFalse(out["merged"]); self.assertIn("approval", out["missing"][0])
def test_land_reports_failed_and_pending_checks(self): ...                 # "check validate failed" / "checks still running"
def test_land_falls_back_to_squash_when_merge_commits_are_disabled(self): ...
```

- [ ] **Step 2: Run, expect failures** (`No module named pb_core.merge`).

- [ ] **Step 3: Implement `merge.py`**

- `merge_start`: fetch; `files` = `git diff --name-only origin/<default>...origin/docs/brain` not under `brain/`. If any: return the alert without creating the worktree. Else `git worktree add --detach <worktree> origin/docs/brain`, `git merge --no-commit --no-ff origin/<default>`. Unmerged paths outside `brain/` (should not happen once the first check passed, but a rename can cause it): `git merge --abort`, remove the worktree, same alert. Classify the unmerged paths: `GENERATED` → `generated`, `brain/.pb/state/` → `state` (resolve at once with the `docs/brain` side and `git add`), `brain/schema/` and `brain/.pb/toolkit/` → `schema`, the rest → `pages`. `changed` comes from `git diff --name-only <base> <side> -- brain` minus generated files.
- `merge_finish`: `unresolved` = unmerged paths that are not generated; stop if any. Take either side of the generated files, `generate(brain)`, `git add brain`, run the save checks on every page in `changed` of both sides plus the resolved ones, commit with `message`, `git push origin HEAD:refs/heads/docs/brain`.
- `merge_land`: `ensure_brain_pr`; poll `repos/<owner>/commits/<head sha>/check-runs` every 15 s up to `wait`; read `repos/<owner>/pulls/<n>` for `mergeable_state` (`blocked` with all checks green → `missing: ["an approval or another rule of <base> (see the PR)"]`); merge with `PUT repos/<owner>/pulls/<n>/merge`, `merge_method: "merge"`, and on HTTP 405 for a disallowed method retry with `squash`. Never pushes to the default branch.

- [ ] **Step 4: Write `skills/merge/SKILL.md`**

Frontmatter `name: merge`; description: "Brings what the routine wrote on `docs/brain` to the default branch: merges the default branch into `docs/brain`, resolves brain conflicts and inconsistencies, asks when sources do not settle one, and merges the Brain updates PR. Use when the user asks to merge, land or publish the brain updates or the routine's changes, or when `docs/brain` is behind or in conflict." Body, in the order of spec §5b:
1. `PB merge start --worktree <tmp>`; on `alert`, show `files`, say they must go to a code PR, stop.
2. Resolve `conflicts.pages` (combine both versions by the type's writing rules in `references/writing.md`, then `git -C <tmp> add`); for `conflicts.schema` ask the person, one question per file.
3. Inconsistencies: read `git -C <tmp> diff <base> origin/docs/brain -- <changed.routine>` and the same for `changed.default`, and look for the four kinds listed in the spec. Fix what sources or dates settle; otherwise ask one question per inconsistency with both versions and their sources; "I don't know" → an `open-question` page.
4. `PB merge finish --worktree <tmp> -m "pb(merge): bring <default> into docs/brain"`; fix `errors` and repeat.
5. `PB merge land`; on `missing`, say exactly what and from whom, and that running `/pb:merge` again will finish.
6. `PB routine cleanup --worktree <tmp>`; report pages combined (what was kept from each side), inconsistencies fixed, questions asked, open questions created, whether the default branch has the changes.

Never asks to confirm a step; never touches the user's checkout; never pushes to the default branch.

- [ ] **Step 5: Run the whole suite, expect OK** (`test_plugin_layout` sees the new skill).
- [ ] **Step 6: Commit** `feat(merge): /pb:merge brings the routine's changes to the default branch`

---

### Task 5: CI, scaffold and init

**Files:**
- Modify: `templates/github/pb-validate.yml`, `scripts/pb_core/scaffold.py`, `skills/init/SKILL.md`, `skills/routine-setup/SKILL.md`
- Delete: `templates/github/pb-brain-branch.yml`
- Test: `tests/test_scaffold.py`, `tests/test_e2e.py`

**Interfaces:**
- Produces: `WORKFLOWS = ("pb-validate.yml",)`; `scaffold()` and `upgrade()` write `brain/.gitattributes`; `upgrade()` deletes `.github/workflows/pb-brain-branch.yml` and reports it in its `deleted` list.

- [ ] **Step 1: Write the failing tests**

```python
def test_scaffold_writes_one_workflow_and_gitattributes(self):
    self.assertFalse((repo / ".github/workflows/pb-brain-branch.yml").exists())
    attrs = (repo / "brain/.gitattributes").read_text()
    for line in ("index.md linguist-generated", "glossary.md linguist-generated", "features.md linguist-generated",
                 "context/** linguist-generated", ".pb/backlinks.json linguist-generated"):
        self.assertIn(line, attrs)
def test_upgrade_removes_brain_branch_workflow(self): ...
def test_validate_workflow_shape(self):
    text = (ROOT / "templates/github/pb-validate.yml").read_text()
    self.assertNotIn("push:", text)
    self.assertIn("Generated files are stale: run `PB generate` and commit", text)
    self.assertIn("review:", text); self.assertIn("pull-requests: write", text)
    self.assertIn("brain-only:", text)
```

- [ ] **Step 2: Run, expect failures.**

- [ ] **Step 3: Implement**

- `pb-validate.yml`: trigger `pull_request` only. In `validate`, after the page check and only when files under `brain/` changed in the PR: `python3 "$toolkit" --brain brain generate`, then fail with the message above if `git status --porcelain -- brain` is not empty (the checkout is the PR's merge result). New job `review` with `permissions: { contents: read, pull-requests: write }`: `python3 "$toolkit" --brain brain review --base "$BASE" --no-noise`, append its `markdown` and any changed file under `brain/schema/` or `brain/.pb/toolkit/` to `$GITHUB_STEP_SUMMARY`, request `reviewers.users`/`reviewers.teams` with `gh api repos/$REPO/pulls/$NUMBER/requested_reviewers`; a failed request prints a warning and the job still passes (S7). `brain-only` unchanged.
- `skills/init/SKILL.md`: the "how the brain lives" paragraph and section 7 follow spec §8: commit in the temporary worktree, `git push origin HEAD:refs/heads/pb/init`, `gh pr create --head pb/init --base <default> --title "Create the project brain"`. Remove the `docs/brain` protection and workflow-push checks (move the protection check to `skills/routine-setup/SKILL.md`: `docs/brain` must accept pushes from the routine owner and from whoever runs `/pb:merge`). Remove the `pb-brain-branch`/`PB_BRAIN_TOKEN` text. Section U (upgrade) becomes README §9 of the spec. The pipeline advice keeps only `paths-ignore: ["brain/**"]` for PRs touching nothing else.

- [ ] **Step 4: Run the whole suite, expect OK.**
- [ ] **Step 5: Commit** `feat(ci): freshness check and review job; init opens an ordinary PR`

---

### Task 6: Skills, references, routine prompt

**Files:**
- Modify: `references/conventions.md`, `references/writing.md`, `references/reader.md`, `skills/{capture,put,fix,meeting,lint,schema,sync,routine-run,setup,ask,context}/SKILL.md`, `templates/routine/prompt.md`, `templates/brain/AGENTS.md`, `templates/brain/README.md`, `scripts/pb_core/scaffold.py` (`_refresh_agents` anchors on a sentence of `AGENTS.md`)
- Test: `tests/test_plugin_layout.py`, `tests/test_routine_options.py`, `tests/test_scaffold.py`

**Interfaces:**
- Consumes: the CLI of Tasks 1–4 exactly as named there.

- [ ] **Step 1: Write the failing test**

```python
def test_no_stale_model_in_shipped_text(self):
    banned = ("PB workspace sync", "pb workspace", "save --continue", "--force-review", "pb/review/",
              "pb-brain-branch", "PB_BRAIN_TOKEN", "managed copy", "review PR")
    for path in [*ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("references/*.md"), *ROOT.glob("templates/**/*.md")]:
        text = path.read_text()
        for word in banned:
            self.assertNotIn(word, text, f"{path.name}: {word}")
def test_read_mode_reads_the_default_branch(self):
    self.assertIn("default branch", (ROOT / "skills/ask/SKILL.md").read_text())
    self.assertNotIn("docs/brain", (ROOT / "skills/ask/SKILL.md").read_text())
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Rewrite the texts**

- `conventions.md` **Modes**: *Repo mode* = `brain/` of the current checkout, on the branch the developer is on; pb never commits or pushes there. *Routine run* = `docs/brain` in a checkout or temporary worktree (`PB routine start/finish`); used by the scheduled routine, `/pb:sync` and `/pb:routine-run --local`. *Read mode* = the default branch through the GitHub connector. Command table: `PB save [PATH…]`, `PB retention`, `PB merge start|finish|land`, `PB generate` (safe by hand; it resolves a conflict on generated files), no `workspace`.
- `writing.md` **Before writing**: no sync step. **Closing flow**: `PB save <files written>`; on `errors` fix and repeat; then tell the user in one message the files changed and that they are uncommitted in the branch `<branch>`; when `watched` is not empty, name the points and the reviewers who will be asked on the PR; when `on_default`, say the pages need a branch and a PR like any change. Commit only if the user asks (`PB commit -m …`). **Conflicts**: a conflict on generated files is resolved by `PB generate`; page conflicts in a working branch are the developer's.
- `sync` and `routine-run`: always a routine run on `docs/brain` in a temporary worktree, never the user's checkout; report `pr`, `watched`, `behind` from `PB routine finish`; when `behind > 0` name `/pb:merge`.
- `templates/routine/prompt.md`: the result keys of Task 3; "never merge branches; never open pull requests any other way".
- `setup`: for developers; drop the workspace step and the "saving never needs git" wording.
- `ask`, `context`, `reader.md`: read mode reads the default branch.
- `AGENTS.md` template: "The brain in this checkout is the brain of your branch. Write pages here with the `pb` skills and commit them with your code."; update the anchor string in `scaffold._refresh_agents` to match.

- [ ] **Step 4: Run the whole suite, expect OK.**
- [ ] **Step 5: Commit** `docs(skills): skills and references follow the working-branch model`

---

### Task 7: README, version, spikes

**Files:**
- Modify: `README.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `scripts/pb_core/__init__.py`, `presets/software-product/VERSION` (only if it tracks the plugin version), `docs/spikes.md`, `docs/specs/2026-10-31-project-brain-design.md` (one line at the top: superseded in part by the 2026-11-11 spec)
- Test: `tests/test_plugin_layout.py`, `tests/test_cli.py`

- [ ] **Step 1: Failing test:** `pb version` and `plugin.json` both report `0.5.0`; `README.md` contains `/pb:merge` and does not contain `pb-brain-branch`.
- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Rewrite**
  - README: the "Who" table (developers: Claude Code, in their branch; PMs, designers, analysts, QA: Cowork, read-only from the default branch; maintainer: `/pb:merge`), the mermaid flow (sessions → working branch → code PR → default branch; routine → `docs/brain` → `/pb:merge` → default branch; Cowork reads the default branch), "How saving works", "Set up" (init opens a PR; no step 1b for non-developers), commands table (add `/pb:merge`), "Upgrading" (spec §9), troubleshooting (remove offline, lock, review-PR and `pb-brain-branch` rows; add "The brain PR is in conflict → `/pb:merge`", "CI says generated files are stale → `PB generate`, commit").
  - `plugin.json` description: "…a typed, linked product wiki in the monorepo (`brain/`), fed by developers in their branches and by a routine reading Teams, Confluence, Jira and GitHub, built for AI agents."
  - `docs/spikes.md`: S1 reads the default branch; S2 as in the spec; S6 replaced by S6′; add S7.
- [ ] **Step 4: Run the whole suite, expect OK.**
- [ ] **Step 5: Commit** `docs: README in line with 0.5; version 0.5.0`
