# Study — token usage

Status: analysis and proposals, not implemented. Date: 2026-10-31.

Questions:
1. Which operations can run **without AI** at no loss of quality?
2. Which habits **save tokens without losing data**?

## Where the tokens go

Estimates for a mid-size team in one nightly routine run: 3 Teams channels, 2 Confluence spaces, 2 recurring meetings, about 20 merged PRs, a brain of about 300 pages. They are orders of magnitude to rank the work, not measurements.

| Item | Size per run | Share | Can the toolkit read it instead? |
|---|---|---|---|
| Meeting transcripts | 2 × ~10k words | very high | no: connector only |
| Teams threads | ~150 messages × ~60 words ≈ 9k words | high | no: connector only |
| Confluence pages changed | ~5 × 1.5k words | medium | no: connector only |
| Merged PRs (list, files, bodies) | ~20 PRs | medium | **yes**: `gh` is a CLI |
| Brain pages read to update them | ~10–20 pages | medium | partly |
| Fixed instructions (prompt, `sync` skill, conventions, schema, AGENTS.md) | ~5.6k words ≈ 7.5k tokens | low per run, paid on every run | — |
| Pages written (output tokens, ~5× the price of input) | ~10 pages | medium | partly |
| Accumulated context: everything read early is re-sent on every later turn | grows with the run | **the hidden multiplier** | — |

Two structural facts follow:
- **Connector data always passes through the model.** The toolkit cannot call MCP connectors: Teams, Confluence, Jira and meeting content is necessarily read by an LLM. Savings there come from *which* model reads it and *how long it stays in context*, not from skipping it.
- **The agent loop re-sends the context at every turn.** Prompt caching makes re-reads cheap (about a tenth of the price), but a run that reads 30k words of transcripts in its first turns pays for them again over 50–100 turns. Isolating raw content is worth more than shortening instructions.

## 1. Operations that can run without AI, with no quality loss

| # | Operation today | Deterministic replacement | Saving |
|---|---|---|---|
| D1 | `sync` GitHub: the LLM lists PRs, reads file lists, maps them to modules, skips unrelated PRs | `pb prs --since <cursor>`: the toolkit calls `gh api`, filters merged PRs, matches files against `module.paths` and returns only matching PRs with title, body excerpt, modules and diff stats. It also moves the cursor | All unrelated PRs and file lists leave the context (typically most of them); fewer turns |
| D2 | `PB resolve` called once per entity: one turn each | `PB resolve` with several names in one call | Turns, so context re-sends |
| D3 | `ask` / `brief onboarding` read all of `index.md` (one line per page: ~10k tokens at 300 pages, growing) | `pb search <terms>`: ranked hits over titles, aliases, summaries and glossary terms; read the index only when the search is empty | Constant cost instead of one that grows with the brain |
| D4 | The LLM writes frontmatter and section headings of each new page, and validation catches mistakes | `pb new <type> "<title>"` writes the skeleton (implicit fields, dates, required fields, body sections from the type) | Output tokens and validate–fix turns |
| D5 | The LLM composes the whole digest | The toolkit fills the mechanical sections (brain size, counts, cursors, deferred and failed items) from a run log that `pb` commands append to; the LLM writes only the "Ingested" one-liners | Output tokens; also more reliable digests |
| D6 | Thread grouping, the 24-hour deferral and cursor arithmetic are done by the LLM | Not replaceable: the messages arrive through the connector | — |

D1 is the clear win: it removes a whole class of reading from the model with no judgement lost, because matching file paths to modules is already a toolkit function (`modules_for_paths`).

## 2. Saving tokens without losing data

| # | Measure | What it saves | Data lost |
|---|---|---|---|
| T1 | **One subagent per raw source**, on a cheaper model (e.g. Sonnet or Haiku). It reads the threads, pages or transcript and returns structured candidate facts with their references. The main session only resolves, decides and writes. | Raw content never enters the main context: no re-send multiplier. The bulk of the reading runs at a lower price. | None if the subagent extracts with the same rules and keeps every reference. Classification is the job small models do well; deciding and writing stays with the main model. |
| T2 | **Edit, don't rewrite**: update existing pages with targeted edits instead of rewriting the whole file | Output tokens, the most expensive kind | None |
| T3 | **Split the conventions**: read-only skills (`ask`, `context`, `brief`) load only "Modes", "Connectors" and "Page format"; writing skills also load the writing rules | About 1.5k tokens per read-only call, frequent in Cowork | None |
| T4 | **Triage memory**: store `{thread id: last reply time, verdict}` in the Teams state. Unchanged threads classified as `ignore` or `signal` are not re-triaged; deferred threads are re-read only when a new reply arrives | Repeated reasoning over the same threads | None: a new reply always triggers a new triage |
| T5 | **Ask connectors for less**: narrow date windows, required fields only, page sizes matched to the cursor; for Confluence, compare versions from the search result before fetching any body | Payload size | None |
| T6 | **Routine model**: run the scheduled routine on Sonnet rather than the most capable model. Interactive commands keep the user's model | Price per token of the biggest job | Low; check with a side-by-side run on the same day |
| T7 | **Never re-read what is in context**: no `index.md` after `PB context` already returned the pages; no second read of a page just written | Turns and input | None |

### Not recommended: they would lose data or quality
- Skipping threads or pages by length or keywords before reading them.
- Truncating transcripts or reading only the meeting chat.
- Letting the small model write pages: the significance gate and consolidation need the strong model.
- Dropping the 24-hour deferral to save a re-read: threads would be ingested half-finished.

## Measuring before and after

Today nothing measures what a run costs. Proposals:
- `/pb:routine-run status` reads the run logs of the cloud routine (`list_runs` / `get_run_log`). If they report usage, write it in the digest under "Brain size" as "Run cost". **Spike:** check whether the logs expose token usage.
- Without that, use proxies the toolkit can count: words read per source (subagents report them), turns, pages written. Run one week before and one week after T1 and D1.

## Suggested order

1. **D1 `pb prs`**: deterministic, small, testable, no quality risk.
2. **T1 subagents per source** for meetings and Teams: by far the largest saving. Spike first: subagent availability and model choice inside cloud routines.
3. **T2 + T3 + T7**: instruction-only changes, cheap to make.
4. **D2, D3, D4**: toolkit conveniences that cut turns and output.
5. **T4 triage memory** and **D5 digest skeleton**, once the routine has run for a few weeks and the re-read cost is visible.

Effort: D1 about half a day; T1 about a day plus a spike; T2/T3/T7 about two hours; D2–D4 about a day together.
