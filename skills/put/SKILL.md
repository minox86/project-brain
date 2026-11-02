---
name: put
description: Feeds the project brain with content — pasted text or notes, local files (PDF, docx, markdown), Confluence pages, Jira issues or JQL, GitHub PRs or issues, Figma links, web pages — extracting features, epics, concepts, modules, interfaces, decisions and open questions and updating the right pages. Use when the user says to add, ingest, import or save something into the brain, or shares knowledge to remember ("we decided that…", "the billing service actually…").
argument-hint: "<text | file | confluence:… | jira:… | gh:pr/N | url> [--as <type>] [--plan]"
---

# /pb:put — feed the brain

Arguments: `$ARGUMENTS`

## 0. Before starting

1. Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only (read mode: give the read-only reply).
2. Read `brain/AGENTS.md`, `brain/schema/brain.md`; list types with `ls brain/schema/types`.
3. Options: `--as <type>` fixes the main type; `--plan` forces showing the plan before writing.
4. No input: ask "What do you want to put in the brain?".

## 1. Classify and read the input

| Input | How to recognise it | How to read it |
|---|---|---|
| Free text | anything that is not a reference | as is |
| Local file or folder | the path exists | Read (PDF via Read); a folder is a batch, one file at a time |
| Confluence | `…atlassian.net/wiki/…` URL or `confluence:<SPACE>/<id>` | Atlassian connector: `getConfluencePage` |
| Jira | `jira:<KEY>`, or `jira: <JQL>` (batch) | `getJiraIssue` / `searchJiraIssuesUsingJql`; an Epic becomes an `epic` page |
| GitHub | `gh:pr/<n>`, `gh:issue/<n>`, or a github.com URL | `gh api repos/{owner}/{repo}/pulls/<n>` (+ `/files`), `…/issues/<n>` |
| Figma | figma.com URL | Figma connector if available; otherwise ask the user for the relevant notes |
| Web | other http(s) URL | WebFetch |

If the connector or tool for the input is missing, guide the user as **Connectors** in the conventions says before anything else, and offer to continue from pasted text or an exported file. Never rebuild content from memory.

## 2. Capture local files

A file versioned in the monorepo (`git ls-files --error-unmatch <path>` succeeds) is not captured: it stays authoritative in the repo; summarise it and cite it as `repo:<path>`.

For any other local file (not for external sources, not for pasted text):
- extract the text and write `brain/raw/YYYY/MM/YYYY-MM-DD-<slug>.md`:

      ---
      kind: file
      captured: 2026-10-31
      origin: <original file name>
      link: <SharePoint/Confluence/Figma URL, if any>
      ---
      <extracted text, intact>

- never copy the binary into the repo. If the file has no stable external home, ask the user to upload it (SharePoint, Confluence, Figma) and give you the link; record it in `link`;
- if the extracted text exceeds `raw_max_words` (from `brain.md`), store a faithful summary instead of the full text, and say so in the body;
- cite it as `raw:YYYY/MM/YYYY-MM-DD-<slug>`.

`raw/` is immutable after capture.

## 3. Analyse

1. Extract candidate knowledge: features and their expected behaviour, scope agreements, constraints and risks of an epic in progress (on its `epic` page; what stays true after delivery goes on features and decisions), domain concepts (with the Italian term if used), modules and interfaces and their non-obvious behaviour, decisions (with options and reasons), open questions, contradictions with what the brain says.
2. Apply the **significance gate** to each item. Drop what fails it.
3. Resolve every entity with `PB resolve`; prefer updating existing pages.
4. For external requirement detail (PRD, acceptance criteria) keep only a short summary and the link: the source stays authoritative.
5. Contradiction with the brain → `open-question` citing both sources, never a silent overwrite.

## 4. Plan

Prepare the list of changes: page · create/update · what changes, one line each.

Show it and wait for confirmation if `--plan`, or if a new page resembles an existing one, a type is uncertain, a contradiction was found, or more than 5 pages change. Otherwise proceed.

## 5. Write and close

Write pages following each type's prose and budget; set `created`/`updated`, `summary`, `sources`; cite inline. Then the closing flow (`PB save -m "pb(put): <summary>" <files written>`).
