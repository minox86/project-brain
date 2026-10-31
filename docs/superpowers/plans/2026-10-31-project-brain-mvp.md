# project-brain MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `pb` Claude plugin: a deterministic Python toolkit plus skills that keep a typed, linked product wiki in `brain/` inside a monorepo, fed by devs and a nightly routine, readable from Cowork.

**Architecture:** "LLM for semantics, toolkit for mechanics." `scripts/pb.py` is a stdlib-only CLI (JSON on stdout) for validate/resolve/context/generate/stats/lint/state/git/scan/scaffold. Skills under `skills/<name>/SKILL.md` drive the LLM work and call the toolkit. `pb scaffold` vendors the toolkit into `brain/.pb/toolkit/` so CI workflows in the monorepo can run it without access to the plugin repo.

**Tech Stack:** Python 3.9+ standard library only, `unittest`, git, GitHub Actions YAML, Claude plugin format (`.claude-plugin/plugin.json`).

**Spec:** `docs/specs/2026-10-31-project-brain-design.md`

## Global Constraints

- Python **3.9** compatible (local interpreter is 3.9.6): no `match`, no `X | Y` type unions at runtime, no third-party packages.
- Toolkit lives in `scripts/` (`scripts/pb.py` + `scripts/pb_core/`). **No `bin/` directory** in the plugin.
- Skills call the toolkit as `PB = python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pb.py"`.
- Every CLI command prints one JSON object on stdout. Exit `0` ok, `1` findings (described in JSON), `2` usage/environment error (`{"error": "..."}`).
- Brain root resolution: `--brain <dir>` → env `PB_BRAIN` → walk up from cwd looking for `brain/schema/VERSION` (the brain dir is the `brain/` folder; the repo root is its parent).
- Everything in English. Glossary bilingual via `term_en` / `term_it`.
- Generated paths (never committed by skills, only by CI): `brain/index.md`, `brain/glossary.md`, `brain/context/`, `brain/.pb/backlinks.json`.
- Defaults from spec: digest retention 30 days; budgets concept 200, open-question 200, decision 400, environment 300, interface 400, feature 600, module 600.
- Plugin name `pb`, marketplace name `project-brain`.

## Review Focus

1. **Malformed or missing frontmatter** on one page → `validate` reports an error for that page; `generate`, `context`, `lint`, `stats` skip it and never crash. (Task 3 + Task 4 tests.)
2. **CRLF line endings / BOM** in a page written on Windows → parsed identically to LF. (Task 2 test.)
3. **Wikilink variants** `[[Title|label]]`, `[[Title#Heading]]`, `[[alias]]` → resolve to the same page; alias form is a warning, not an error. (Task 3 + Task 4 tests.)
4. **Empty brain** (scaffolded, zero pages) → `validate`, `generate`, `stats`, `lint`, `context --paths x` all succeed with empty results. (Task 6 + Task 7 tests.)
5. **Module `paths` forms**: `apps/billing/**`, `apps/billing/`, `apps/billing` and an exact file → all match `apps/billing/src/x.ts` (except the exact-file one). (Task 5 test.)

---

### Task 1: Plugin skeleton and CLI entry point

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.gitignore`, `scripts/pb.py`, `scripts/pb_core/__init__.py`, `scripts/pb_core/errors.py`, `scripts/pb_core/cli.py`
- Test: `tests/helpers.py`, `tests/test_cli.py`, `tests/test_plugin_layout.py`

**Interfaces:**
- Produces: `pb_core.__version__ = "0.1.0"`, `pb_core.FORMAT_VERSION = 1`; `errors.PbError(Exception)` with optional `payload`, subclasses `UsageError`, `FrontmatterError`, `NotInBrain`, `GitError`; `cli.main(argv) -> int`; `cli.build_parser()` with subcommands registered via `sub.add_parser(name).set_defaults(handler=fn)` where `fn(args) -> (dict, int)`. `tests/helpers.run_cli(*argv) -> (code, data, stderr)` and `tests/helpers.make_brain(tmp, files: dict) -> Path` (writes a minimal schema from `presets/software-product` plus given files under `<tmp>/brain`, returns repo root).

- [ ] **Step 1:** `git init` in `project-brain/`; write `.gitignore` (`__pycache__/`, `.DS_Store`, `*.pyc`).
- [ ] **Step 2: Write failing tests** — `test_cli.test_version`: `run_cli("version")` → code 0, `data["version"] == "0.1.0"`, `data["brain"] is None` when cwd has no brain. `test_plugin_layout`: `plugin.json` name `pb`; marketplace plugin `source == "./"`; no `bin/` dir; every `skills/*/SKILL.md` has frontmatter `name` equal to its folder and a non-empty `description` (vacuous until Task 11).
- [ ] **Step 3:** Run `python3 -m unittest discover -s tests -v` → FAIL.
- [ ] **Step 4:** Implement manifests, `errors.py`, `cli.py` (`main`, `_emit`, `version` command returning `{"version", "format", "brain"}`), `scripts/pb.py` (adds its dir to `sys.path`, `sys.exit(main())`).
- [ ] **Step 5:** Tests pass. Commit `feat: plugin skeleton and pb CLI`.

### Task 2: Frontmatter parser

**Files:** Create `scripts/pb_core/frontmatter.py`; Test `tests/test_frontmatter.py`

**Interfaces:**
- Produces: `split(text) -> (fm_text | None, body)`; `parse(text) -> (meta: dict | None, body: str)`; `parse_value(s)`. Raises `FrontmatterError` with line number.

Grammar (restricted YAML): top-level `key: value`; `key:` + indented block that is either a list (`- item`, items may be inline maps) or a one-level map (`sub: value`, values may be inline maps/lists); values: quoted strings (`"…"`, `'…'`), bare strings, ints, floats, `true/false`, `null/~`, inline lists `[a, "b"]` and inline maps `{k: v, k2: [x]}` nestable; `#` comments at line start or after whitespace outside quotes; bare value starting with `[[` is a string; dates stay strings.

- [ ] **Step 1: Failing tests:** `test_scalars`, `test_inline_list_and_map` (`fields: {kind: list, of: link, to: module}` inside a block map → nested dict), `test_block_list_of_inline_maps` (`teams:\n  - {id: a, channel: "Gen, eral"}` → list of dicts, comma inside quotes kept), `test_wikilink_bare_value` (`affects: [[X]]` → `"[[X]]"`), `test_crlf_and_bom` (same result as LF), `test_unclosed_frontmatter_raises`, `test_no_frontmatter_returns_none`, `test_comment_stripping` (`a: b # c` → `"b"`, `a: "b # c"` → `"b # c"`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. **Step 5:** Commit `feat: restricted YAML frontmatter parser`.

### Task 3: Brain model (schema, pages, links, resolve)

**Files:** Create `scripts/pb_core/brain.py`, `scripts/pb_core/links.py`, `scripts/pb_core/resolve.py`; Create preset `presets/software-product/` (needed by `make_brain`): `VERSION` (`1`), `brain.md`, `sources.md`, `types/{feature,concept,module,interface,environment,decision,open-question}.md`; Test `tests/test_brain.py`, `tests/test_resolve.py`

**Interfaces:**
- Produces in `brain.py`:
  - `find_brain(start: Path, explicit: str | None) -> Path | None` (returns the `brain/` dir).
  - `class Brain(root: Path)`: `.root` (brain dir), `.repo_root`, `.config: dict` (from `schema/brain.md` merged over `DEFAULTS`), `.types: dict[str, TypeDef]`, `.sources: dict` (frontmatter of `schema/sources.md`), `.pages() -> list[Page]` (cached; only files under type folders), `.load_errors: list[dict]` (`{"path","error"}` for pages whose frontmatter fails), `.by_title: dict[str, Page]`, `.by_alias: dict[str, Page]` (lowercased keys), `.lookup(name) -> (Page | None, "title" | "alias" | None)`.
  - `TypeDef(name, area, folder, fields: dict, required: list, max_words: int | None, system: bool, prose: str)`.
  - `Page(path, rel, title, type, meta, body, words)`; `words` = whitespace-split count of body.
  - `DEFAULTS = {"product": None, "glossary_languages": ["en","it"], "archive_after_days": 90, "open_question_stale_days": 30, "digest_retention_days": 30, "context_pack_max_words": 4000, "raw_max_words": 3000}`.
  - `GENERATED = ["index.md", "glossary.md", "context/", ".pb/backlinks.json"]` (relative to brain dir).
- `links.py`: `WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")`; `extract(text) -> list[str]` (targets, stripped); `meta_links(meta, typedef) -> list[str]` (targets in `link` and `list of link` fields, plus any `[[...]]` string in `affects`/`resolves`/`resolved_by`).
- `resolve.py`: `resolve(brain, name, type=None) -> list[{"title","path","type","match","score"}]`, match ∈ `title`(1.0) / `alias`(0.95) / `partial`(0.75, substring either way, normalized) / `fuzzy`(difflib ratio ≥ 0.6), sorted by score desc, max 5. CLI: `pb resolve "<name>" [--type T]` → `{"candidates": [...]}`.

Preset values (copy into type files; prose per spec §3.3 and §3.6 — "create when / do not create when / body structure" plus "Keep it under N words"):

| type | area | folder | max_words | system | fields |
|---|---|---|---|---|---|
| feature | functional | functional/features | 600 | no | `status` enum [idea, planned, in-progress, released, deprecated] default idea; `jira` list of string; `modules` list of link→module; `concepts` list of link→concept; `figma` string |
| concept | functional | functional/concepts | 200 | no | `term_en` string; `term_it` string; required [term_en] |
| module | technical | technical/modules | 600 | no | `paths` list of string; `owner_team` string; `interfaces` list of link→interface; `depends_on` list of link→module; required [paths] |
| interface | technical | technical/interfaces | 400 | no | `kind` enum [rest, event, grpc, lib, ui-contract]; `provided_by` link→module; `consumed_by` list of link→module; `spec_path` string |
| environment | technical | technical/environments | 300 | no | `kind` enum [dev, staging, prod, other]; `url` string |
| decision | cross | decisions | 400 | yes | `area` enum [functional, ux, technical]; `status` enum [proposed, accepted, superseded] default accepted; `date` date; `supersedes` link→decision; `affects` list of link; `resolves` list of link→open-question; required [area] |
| open-question | cross | open-questions | 200 | yes | `area` enum [functional, ux, technical]; `status` enum [open, resolved, dropped] default open; `resolved_by` link→decision; `affects` list of link; required [area] |

Implicit fields for every type: `type`, `title`, `aliases`, `summary` (one line, used by index), `created`, `updated`, `sources`.

- [ ] **Step 1: Failing tests:** `test_find_brain_walks_up`, `test_find_brain_env_and_explicit`, `test_types_loaded_from_preset` (7 types, `decision.system is True`, `concept.max_words == 200`), `test_pages_and_lookup` (title + alias lookup, case-insensitive), `test_bad_frontmatter_goes_to_load_errors` (one broken page does not hide the others), `test_wikilink_variants` (`[[A|x]]`, `[[A#h]]`, `[[A#h|x]]` → `["A","A","A"]`), `test_resolve_ranking` (title > alias > partial > fuzzy; `--type` filters).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement + preset files. **Step 4:** PASS. **Step 5:** Commit `feat: brain model, links, resolve and software-product preset`.

### Task 4: Validate (schema, links, secrets, budgets)

**Files:** Create `scripts/pb_core/validate.py`, `scripts/pb_core/secrets.py`; Test `tests/test_validate.py`, `tests/test_secrets.py`

**Interfaces:**
- Consumes: `Brain`, `links`, `frontmatter`.
- Produces: `validate(brain, paths: list[str] | None = None) -> {"errors": [...], "warnings": [...]}`; each finding `{"path","code","message"}`. CLI `pb validate [paths…]` → exit 1 if any error, 0 otherwise (warnings never fail). `secrets.scan(text) -> list[{"line","kind"}]`.

Error codes: `frontmatter` (parse error), `missing-type`, `unknown-type`, `missing-title`, `title-mismatch` (file name ≠ title), `bad-title-chars` (`\ / : * ? " < > | # ^ [ ]`), `duplicate-title` (across brain, case-insensitive, incl. alias colliding with another title), `wrong-folder`, `missing-required`, `bad-enum`, `bad-date` (ISO `YYYY-MM-DD`), `bad-kind` (list expected, etc.), `broken-link` (body or field), `secret`. Warning codes: `unknown-field`, `alias-link` (link via alias), `link-type` (field link target of wrong type), `over-budget` (`words > max_words`, message includes both numbers). `raw/` files: only `secret` and `frontmatter` checks; `raw/` with `words > raw_max_words` → warning `raw-too-long`. Files under `digests/`, `schema/`, generated paths, `AGENTS.md` are not pages; `digests/` and `AGENTS.md` still get `secret` scanning.

Secret patterns (`secrets.py`): AWS `AKIA[0-9A-Z]{16}`; GitHub `gh[pousr]_[A-Za-z0-9]{36,}` and `github_pat_[A-Za-z0-9_]{40,}`; Slack `xox[baprs]-[A-Za-z0-9-]{10,}`; `-----BEGIN [A-Z ]*PRIVATE KEY-----`; JWT `eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}`; credentials in URL `[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/]{3,}@`; assignment `(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*["']?[^\s"'<>]{8,}`.

- [ ] **Step 1: Failing tests:** one test per error code with a minimal page; `test_alias_link_is_warning`; `test_over_budget_warning_not_error` (exit 0); `test_secret_in_body_fails` (each pattern family, plus `password: <placeholder>`-style `password: ${DB_PASSWORD}` does NOT match because `$`/`{` excluded? → assert it is not flagged); `test_paths_argument_limits_scope_but_duplicates_checked_globally`; `test_malformed_page_does_not_crash`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement (secret assignment regex value class `[^\s"'<>${}]{8,}`). **Step 4:** PASS. **Step 5:** Commit `feat: pb validate with secret scan and word budgets`.

### Task 5: Context packs and code↔module mapping

**Files:** Create `scripts/pb_core/context.py`; Test `tests/test_context.py`

**Interfaces:**
- Produces: `path_matches(pattern: str, path: str) -> bool`; `modules_for_paths(brain, paths: list[str]) -> list[Page]`; `build_context(brain, *, jira=None, feature=None, paths=None, max_words=None) -> {"seeds": [titles], "pages": [{"title","type","path","included": "full" | "summary"}], "markdown": str, "words": int}`. CLI `pb context (--jira KEY | --feature TITLE | --paths P [P…]) [--max-words N]`.

Matching: normalize to posix, strip leading `./`; pattern ending `/**` or `/` or without glob chars → directory prefix match (`path == p or path.startswith(p + "/")`); otherwise `fnmatch.fnmatchcase`.
Expansion (one hop each, deterministic order by type then title): seeds → features (by `jira` field containing KEY or `sources` containing `jira:KEY`; by title/alias) or modules (by paths). Feature → its `modules`, `concepts`. Module → `interfaces` field + interfaces whose `provided_by`/`consumed_by` reference it + features listing it in `modules`. Then decisions with `status != superseded` whose `affects` hits any collected page, and open-questions with `status == open` whose `affects` hits any collected page. Markdown: `# Context: <seeds>` then sections `## Features`, `## Concepts`, `## Modules`, `## Interfaces`, `## Decisions`, `## Open questions`, each page as `### <title>` + body. If total words > `max_words` (default `config.context_pack_max_words`), replace bodies from the end of the order with `summary` (or first paragraph) + `(see brain/<rel>)` until it fits; mark `included: "summary"`.

- [ ] **Step 1: Failing tests:** `test_path_forms` (Review Focus #5), `test_context_by_paths_expands_interfaces_features_decisions`, `test_superseded_decision_and_resolved_question_excluded`, `test_context_by_jira_via_field_and_sources`, `test_context_unknown_seed_returns_empty` (exit 0, empty pages), `test_max_words_degrades_to_summary`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat: pb context and path-to-module mapping`.

### Task 6: Generate and stats

**Files:** Create `scripts/pb_core/generate.py`, `scripts/pb_core/stats.py`; Test `tests/test_generate.py`, `tests/test_stats.py`

**Interfaces:**
- Consumes: `build_context`, `Brain`, `links`.
- Produces: `generate(brain, today: date) -> {"written": [rel], "deleted": [rel]}`; `stats(brain) -> {"pages", "words", "by_type": {t: {"pages","words"}}, "by_area": {...}, "over_budget": [{"title","words","max"}], "largest": [{"title","words"}] (top 10)}`. CLI `pb generate [--today YYYY-MM-DD]`, `pb stats`.

`generate` writes:
- `index.md`: header line `<!-- generated by pb; do not edit -->`, `# <product or "Product"> brain index`, sections per area (`Functional`, `Technical`, `Decisions`, `Open questions`) and per type, line `- [[Title]] — <summary or first sentence ≤120 chars>`; decisions show `(<status>)`. Archived items (decision `superseded` or open-question `resolved|dropped` whose `updated` is older than `archive_after_days`) are omitted, with a final line `Archived: N pages (not listed).`
- `glossary.md`: table `| English | Italian | Definition |` from `concept` pages sorted by `term_en`; English cell is `[[Title\|term_en]]`, Italian `term_it` or `—`, definition = summary.
- `context/<feature title>.md` for every feature: `build_context(feature=title)` markdown; remove stale files in `context/` not matching a feature.
- `.pb/backlinks.json`: `{title: [titles linking to it]}` sorted.
- Deletes `digests/YYYY-MM-DD.md` older than `digest_retention_days` relative to `today`.

- [ ] **Step 1: Failing tests:** `test_index_groups_and_archives`, `test_glossary_bilingual_sorted`, `test_context_files_written_and_stale_removed`, `test_backlinks`, `test_digest_retention` (31-day-old deleted, 30-day-old kept), `test_empty_brain_generate_and_stats` (Review Focus #4), `test_stats_over_budget_and_largest`, `test_generate_is_idempotent` (second run → identical files).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat: pb generate and pb stats`.

### Task 7: Lint

**Files:** Create `scripts/pb_core/lint.py`; Test `tests/test_lint.py`

**Interfaces:**
- Produces: `lint(brain, today) -> {"findings": [{"code","path","message", "related": [rel]?}], "stats": stats(brain)}`; CLI `pb lint [--today]` → exit 1 if findings.

Codes: everything from `validate` errors (prefixed as-is); `over-budget`; `duplicate-candidate` (two pages of same type with title difflib ratio ≥ 0.85 on lowercased titles, or alias of one equals title/alias of the other); `orphan` (no inbound links and no outbound links; concepts excluded from orphan check if `term_en` present? → no: include all types); `stale-open-question` (`status: open` and `updated` older than `open_question_stale_days`); `archivable` (as in Task 6 archive rule); `dead-module-paths` (module whose every `paths` entry matches no file under `repo_root`, scanned with `os.walk` skipping `.git`, `node_modules`, `brain`); `superseded-referenced` (a non-superseded page's `affects`/body links to a superseded decision without also linking its successor).

- [ ] **Step 1: Failing tests:** one per code; `test_empty_brain_lint_clean` (exit 0).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat: pb lint`.

### Task 8: Sync state and corrections log

**Files:** Create `scripts/pb_core/state.py`; Test `tests/test_state.py`

**Interfaces:**
- Produces: `get(brain, source, key=None)`, `set_(brain, source, key, value)` on `brain/.pb/state/<source>.json` (source ∈ `teams|confluence|github|jira`; others → `UsageError`); `add_correction(brain, page, wrong, right, evidence, today) -> dict` appending a row to `brain/.pb/corrections.md` (creates file with header `# Corrections\n\n| Date | Page | Wrong | Right | Evidence |\n|---|---|---|---|---|`); `suppress(brain, source, claim)` / suppressed list stored under key `"suppressed"` in the same state file (claims corrected by `/pb:fix` that sync must not re-ingest). CLI: `pb state get <source> [key]`, `pb state set <source> <key> <json-value>`, `pb state suppress <source> "<claim>"`, `pb correction --page P --wrong W --right R --evidence E [--today]`.

- [ ] **Step 1: Failing tests:** `test_set_get_roundtrip_json_values`, `test_unknown_source_is_usage_error` (exit 2), `test_correction_appends_and_escapes_pipes`, `test_suppress_dedup`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement (write JSON with `indent=2, sort_keys=True`, atomic via temp file + `os.replace`). **Step 4:** PASS. **Step 5:** Commit `feat: sync state and corrections log`.

### Task 9: Git operations (dev commit, routine start/finish)

**Files:** Create `scripts/pb_core/gitops.py`; Test `tests/test_gitops.py`

**Interfaces:**
- Produces: `commit(brain, message, allow_default=False) -> {"committed": bool, "sha": str|None, "branch": str, "files": [rel]}` — stages `brain/` excluding `GENERATED`, commits only those paths (`git commit -m msg -- <pathspecs>`), refuses with `GitError` code `on-default-branch` (exit 2, payload `{"error","branch"}`) when the current branch equals the default branch (`git symbolic-ref refs/remotes/origin/HEAD`, fallback `main`/`master`) unless `allow_default`; nothing to commit → `committed: false`. `routine_start(brain, branch) -> {"branch","created": bool}` — `git fetch origin`, checkout `branch` tracking `origin/<branch>` if it exists, else create it from the default branch. `routine_finish(brain, branch, message) -> {"committed","pushed": bool, "conflict": bool}` — `commit(..., allow_default=True)`, `git pull --rebase origin <branch>` (on failure `git rebase --abort`, return `conflict: true, pushed: false`, exit 1), then `git push origin HEAD:<branch>`. CLI: `pb commit -m MSG [--allow-default]`, `pb routine start --branch B`, `pb routine finish --branch B -m MSG`.

- [ ] **Step 1: Failing tests** (temp bare remote + clone, git user configured via `-c` env in helper): `test_commit_only_brain_and_excludes_generated` (a staged file outside `brain/` stays uncommitted; `brain/index.md` change not committed), `test_commit_refuses_default_branch`, `test_commit_nothing_to_commit`, `test_routine_start_creates_missing_branch`, `test_routine_finish_pushes`, `test_routine_finish_conflict_aborts_without_push`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement with `subprocess.run([...], cwd=repo_root, capture_output=True, text=True)`. **Step 4:** PASS. **Step 5:** Commit `feat: git operations for dev commits and routine runs`.

### Task 10: Scan and scaffold (bootstrap of a monorepo)

**Files:** Create `scripts/pb_core/scan.py`, `scripts/pb_core/scaffold.py`, `templates/brain/AGENTS.md`, `templates/brain/README.md`, `templates/github/pb-validate.yml`, `templates/github/pb-generate.yml`; Test `tests/test_scan.py`, `tests/test_scaffold.py`

**Interfaces:**
- Produces: `scan(repo_root) -> {"modules": [{"name","path","manifest"}], "specs": [{"path","kind": "openapi"|"asyncapi"|"proto"|"graphql"}], "adrs": [path], "codeowners": path|None, "readmes": [path], "ci": [path], "top_level": [dir]}`. Module candidates: directories (depth ≤ 3, skipping `.git`, `node_modules`, `vendor`, `dist`, `build`, `.venv`, `brain`) containing one of `package.json`, `pyproject.toml`, `setup.py`, `go.mod`, `pom.xml`, `build.gradle`, `build.gradle.kts`, `Cargo.toml`, `*.csproj`, `composer.json`, excluding the repo root itself. Specs: `openapi*.{yaml,yml,json}`, `swagger*.{yaml,yml,json}`, `asyncapi*.{yaml,yml,json}`, `*.proto`, `*.graphql`. ADRs: `*.md` under any dir named `adr`, `adrs`, `decisions`, or `architecture/decisions`. CLI `pb scan [--repo DIR]` (default: git toplevel of cwd).
- `scaffold(repo_root, preset_dir, plugin_root) -> {"created": [rel]}`: refuses if `brain/schema/VERSION` exists (`UsageError`); copies preset into `brain/schema/` (+ empty `proposals.md` with header); creates type folders with `.gitkeep`, `digests/`, `raw/`; writes `brain/AGENTS.md` and `brain/README.md` from templates (placeholder `{{product}}` from `--product`); copies `scripts/pb.py` + `scripts/pb_core/` into `brain/.pb/toolkit/` with `brain/.pb/toolkit/VERSION` = plugin version; writes `.github/workflows/pb-validate.yml` and `pb-generate.yml` (skip if present, report `skipped`); appends to repo `CLAUDE.md` (create if missing) the block between markers `<!-- pb:start -->` / `<!-- pb:end -->`: `For product and domain context read brain/AGENTS.md.` (idempotent); appends `brain/.pb/cache/` to repo `.gitignore` if absent. CLI `pb scaffold [--repo DIR] --product NAME [--preset software-product]`. Also `pb toolkit-sync` → re-copies the vendored toolkit (for plugin upgrades).

Workflow templates:
- `pb-validate.yml`: on `pull_request` with `paths: ["brain/**"]`; job `validate`: checkout, `python3 brain/.pb/toolkit/pb.py validate`; job `automerge` (needs validate, `if: github.event.pull_request.head.repo.full_name == github.repository`): list changed files with `gh pr diff --name-only "$PR"`; if every file starts with `brain/` run `gh pr merge --auto --squash "$PR"`; `permissions: contents: write, pull-requests: write`.
- `pb-generate.yml`: on `push` to default branch with `paths: ["brain/**", "!brain/index.md", "!brain/glossary.md", "!brain/context/**", "!brain/.pb/backlinks.json"]`; run `python3 brain/.pb/toolkit/pb.py generate`, then commit as `github-actions[bot]` with message `pb(generate): refresh generated files [skip ci]` only if `git status --porcelain brain` is non-empty, and push.

`AGENTS.md` template content (concise, ≤ 400 words): how to read (index → glossary → `context/<feature>.md` → pages; `module.paths` maps code to modules), how to write (only through `pb` skills or following `schema/types/*.md`; significance gate and writing rules from spec §3.6 verbatim as bullets; no person names, no secrets, no personal data), authority rules from spec §3.5, and a `## Routine` section placeholder filled by `/pb:routine-setup`.

- [ ] **Step 1: Failing tests:** `test_scan_finds_modules_specs_adrs` (fixture monorepo with `apps/web/package.json`, `services/billing/pyproject.toml`, `services/billing/openapi.yaml`, `docs/adr/0001-x.md`, `node_modules/x/package.json` ignored), `test_scaffold_creates_layout` (schema, folders, AGENTS.md with product name, vendored toolkit runs `version` via subprocess, both workflows, CLAUDE.md markers), `test_scaffold_refuses_existing_brain`, `test_scaffold_claude_md_idempotent`, `test_scaffolded_brain_validates_clean` (Review Focus #4).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat: pb scan and pb scaffold`.

### Task 11: Shared conventions and init/schema skills

**Files:** Create `references/conventions.md`, `skills/init/SKILL.md`, `skills/schema/SKILL.md`

**Interfaces:**
- Consumes: CLI commands from Tasks 1–10 (exact names as defined there).
- Produces: `references/conventions.md`, read by every skill first (path `BASE/../../references/conventions.md`).

`conventions.md` sections: **Toolkit** (`PB` invocation, JSON/exit contract, command table); **Mode detection** (run `PB version`: `brain` non-null → repo mode; else if a GitHub connector/tool can read the monorepo → read mode, reading `brain/index.md` from the default branch; else stop and explain); **Read mode rules** (only `ask`/`context`; write skills reply: knowledge enters through the configured Teams channels and Confluence spaces, or ask a developer to run `/pb:put`); **Page format** (spec §3.2); **Significance gate and writing rules** (spec §3.6, verbatim); **Authority and conflicts** (spec §3.5: contradictions → `open-question`, never silent overwrite); **Privacy** (spec §3.4); **Closing flow** (repo mode: `PB validate <changed>` fix ≤2 times → condense pages with `over-budget` warnings → `PB commit -m "pb(<skill>): <summary>"`; on `on-default-branch` ask the user, then `--allow-default`; never push); **Schema signals** (append to `schema/proposals.md`).

`init` skill: description triggers ("initialise/create the project brain", "set up pb", any `pb` command outside a brain). Flow per spec §4.1: (1) refuse if `PB version` shows a brain; (2) gather facts silently: `PB scan`, read preset `presets/software-product/` (types + `brain.md`), README(s), a sample of ADRs/specs; optional Confluence space / Jira epics only if the user names them; (3) build the design tree of schema decisions (product name; per type keep/extend/drop non-system; extra types; enum values; field additions; budgets; glossary languages; module boundaries and `paths` from scan; Confluence spaces/Teams channels to register now or later via `/pb:routine-setup`); (4) grill in rounds — the exact round format (numbered `❓ **Qn** - **title**: body` + `➡️ recommendation`, "yes" accepts, ask the whole frontier, recompute, never ask facts findable in repo/connectors); (5) confirm full summary; (6) `PB scaffold --product …`, then apply interview results by editing `brain/schema/*` (never removing system types); (7) bootstrap: propose module pages (paths filled), interface pages from specs, decision pages from ADRs (status accepted, area technical), optional features/concepts from Confluence/Jira — confirm in bulk or one by one, apply the significance gate; (8) closing flow (commit on current branch, suggests a dedicated branch first if on default).

`schema` skill: actions `show` (types table), `propose` (from `proposals.md` + lint signals), `apply <Pn>` (edit type files; when a field/type rename affects pages, edit pages too, validate, commit as a dedicated commit `pb(schema): …`; removing a system type is refused).

- [ ] **Step 1:** Write the three files.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_plugin_layout -v` → PASS (skill names match folders). Run `claude plugin validate . --strict` → no errors.
- [ ] **Step 3:** Commit `feat: conventions, init and schema skills`.

### Task 12: Ingestion, query and maintenance skills

**Files:** Create `skills/{put,meeting,capture,fix,sync,ask,context,lint,routine-setup}/SKILL.md`, `templates/routine/prompt.md`

**Interfaces:**
- Consumes: `references/conventions.md`; CLI from Tasks 3–9; MCP tool families: Atlassian Rovo (`getConfluencePage`, `searchConfluenceUsingCql`, `getJiraIssue`, `searchJiraIssuesUsingJql`), Microsoft 365 (`teams_list_teams`, `teams_list_channels`, `teams_list_channel_messages`, `chat_message_search`, `outlook_calendar_search`, `read_resource`), GitHub via `gh api` REST.

Each skill: frontmatter `name`, `description` (with natural-language triggers), `argument-hint`; body starts with "Read `BASE/../../references/conventions.md`" and mode check. Content requirements:
- `put`: input classification table (text, local file/folder, `confluence:`/Confluence URL, `jira:KEY`/`jira: <JQL>`, `gh:pr/N`/PR URL, Figma URL via Figma connector if present, other URL via WebFetch); local files → extracted text into `raw/YYYY/MM/YYYY-MM-DD-<slug>.md` (frontmatter `kind`, `captured`, `origin`, `link`), binaries never copied, ask for an external link if none; if extracted text > `raw_max_words` store a summary instead; then resolve → significance gate → plan (show when new pages, uncertain type, contradictions or >5 pages) → write → closing flow.
- `meeting`: find meeting via calendar search / link; read transcript + chat via `read_resource`; no raw stored; extract decisions, open questions, feature/concept updates; cite `teams:meeting/<id>`; closing flow.
- `capture`: spec §4.3 steps verbatim as the procedure; files touched in session → `PB context --paths …` to find target pages; contradictions → `fix` flow.
- `fix`: spec §4.4 steps; uses `PB resolve`, grep across `brain/`, `PB correction …`, `PB state suppress <source> "<claim>"` when the wrong claim came from an ingested source.
- `sync`: args `[teams|confluence|github|jira] [--check]`; per source: read cursor `PB state get`, fetch incrementally (Teams: per configured channel, messages after cursor, grouped by thread, defer threads with last reply < 24h, triage `ignore|signal|knowledge`; Confluence: CQL `space = X AND lastmodified > "<cursor>"` (or `ancestor = <root_page>`), re-ingest only if version changed; GitHub: `gh api "repos/{repo}/pulls?state=closed&sort=updated&direction=desc"` filtered on `merged_at > cursor`, files via `gh api repos/{repo}/pulls/N/files`, keep PRs touching any module `paths` (`PB context --paths`); Jira: issues linked from features, `updated > cursor`); skip suppressed claims; `--check` reports what would be ingested without writing; update cursors only after successful writes; write `digests/YYYY-MM-DD.md` (ingested / signal / skipped-with-reason / `PB stats` summary) when run by the routine or with `--digest`.
- `ask`: index first, then pages, glossary; answer with citations `[[Title]]` + external refs; if the answer reveals a contradiction with code → suggest `/pb:fix`; read mode supported.
- `context`: wraps `PB context`; in read mode builds the pack by reading `brain/context/<feature>.md` or following links manually.
- `lint`: runs `PB lint`, groups findings, `--fix` proposes merges/condensations/archive moves with preview, applies after confirmation, closing flow.
- `routine-setup`: list teams/channels and Confluence spaces via connectors, user picks; ask target branch (`main` vs long-lived branch, explain trade-off, for `main` warn about branch-protection bypass); write `routine:` (`branch`, `schedule` default `"0 2 * * *"`, `owner_role: Engineering Manager`), `teams:` list of `{id, team, team_id, channel, channel_id}`, `confluence:` list of `{id, space, root_page?}`, `github: {repo}` into `schema/sources.md`; fill the `## Routine` section of `AGENTS.md`; render `templates/routine/prompt.md` with these values and print the `/schedule` instructions (cloud routine on the monorepo, connectors Microsoft 365 + Atlassian enabled); closing flow.
- `templates/routine/prompt.md`: `PB routine start --branch {{branch}}` → `/pb:sync teams confluence github --digest` → `PB validate` (fix ≤2) → `PB routine finish --branch {{branch}} -m "pb(routine): sync {{date}}"`; on `conflict` or persistent validation errors, do not push, and record it at the top of the next digest; never open PRs; `gh pr` is unavailable, use `gh api` REST only.

- [ ] **Step 1:** Write the nine skills and the routine template.
- [ ] **Step 2:** `python3 -m unittest discover -s tests -v` → all PASS; `claude plugin validate . --strict` → no errors.
- [ ] **Step 3:** Commit `feat: ingestion, query, maintenance and routine skills`.

### Task 13: README, spikes checklist, end-to-end smoke test

**Files:** Create `README.md`, `docs/spikes.md`; Test `tests/test_e2e.py`

- [ ] **Step 1: Failing test** `test_e2e_scaffold_write_validate_generate_context`: scaffold a fixture monorepo (`git init`), write one module (paths `services/billing/**`), one interface, one feature, one concept, one accepted decision affecting the module, one open question; `pb validate` exit 0; `pb commit` on a feature branch commits them; `pb generate` writes index/glossary/context; `pb context --paths services/billing/api.py` includes all six titles; `pb lint` has no `broken-link`.
- [ ] **Step 2:** Run → FAIL if any gap; fix in the owning module. → PASS.
- [ ] **Step 3:** `docs/spikes.md`: S1–S5 from spec §8, each with exact manual steps, expected result, and the fallback.
- [ ] **Step 4:** `README.md`: what it is, requirements, install (Claude Code marketplace, Cowork admin sync), commands table, routine setup, development (`python3 -m unittest discover -s tests -v`, `claude plugin validate . --strict`, `claude --plugin-dir .`).
- [ ] **Step 5:** Full test run + plugin validate → clean. Commit `docs: README, spikes checklist and e2e test`.
