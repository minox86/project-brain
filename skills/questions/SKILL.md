---
name: questions
description: Walks through the open questions of the project brain one at a time, in the user's language — shows each with its context, suggests answers drawn from the brain, its sources and the code, takes the user's choice or a free answer, writes the answer into the brain in English and deletes the open question. Use when the user asks to go through, answer, review, close or be asked the open questions, the pending doubts or what is still undecided ("ask me the open questions", "what is still open on approvals?", "let's close the open questions").
argument-hint: "[feature, process, Jira key or area]"
---

# /pb:questions — answer the open questions

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md` and `BASE/../../references/writing.md`. Repo mode only: in read mode, list the open questions with `/pb:ask` and say that answering needs Claude Code.

Speak with the user in their language, the one they write in. Everything written to the brain is in English, whatever language the answer came in; a `concept` page also gets its `term_<lang>` in the glossary languages.

## 1. Collect

The open questions are the pages in `brain/open-questions/` whose `status` is `open` or absent. With arguments, keep those whose `affects` links, `area` or text match the feature or process (`PB resolve`), the Jira key (the features whose `jira` lists it) or the area given. Order them: oldest `updated` first. Say how many there are, in one line; with none, say so and stop.

## 2. One question at a time

For each question, in order:

1. **Prepare.** Read the page, the pages in `affects`, the sources it cites and, for a technical question, the code those pages point to. Work out up to two candidate answers; when the evidence clearly favours one, it is the recommended one. Never invent an answer the evidence does not support: with nothing to go on, offer no suggestion.
2. **Show**, in the user's language and in a few lines: the question, why it matters, what is known so far with its sources.
3. **Ask with `AskUserQuestion`**, one question per call, in the user's language:
   - one option per candidate answer, the recommended one first with "(Recommended)" in its label; each option's description says what it rests on (the page, the source, the code path);
   - an option for "still open, I don't know";
   - an option for "no longer relevant";
   - the free answer is the "Other" the tool always offers: say in the question text that they can write their own.
4. **Apply the answer** (step 3), then go on to the next question. If the user wants to stop, go to the closing flow with what was answered.

Never ask two questions in one call, and never answer a question for the user: a suggestion becomes an answer only when they pick it.

## 3. Write the answer

- **An answer** (a suggested option or a free one; a free answer may need one follow-up question if it does not settle the point):
  - if it is a choice that constrains future work, create a `decision` (title: the outcome; `## Context` carries the question and what was known; `## Options` the alternatives, including the candidates not chosen; `affects` from the question) and apply **Propagation** from the writing rules to the affected pages;
  - if it is a fact, write it on its canonical page (feature, process, concept, role, module, contract, integration…), following **Update before create**;
  - cite the source: the documents the answer rests on, or `session:<YYYY-MM-DD>` when it is the user's own word;
  - then **delete the open-question page** and replace every link to it across the brain (the pages that link it are listed under its title in `brain/.pb/backlinks.json`: Markdown links to its file in bodies, its title in link fields) with `[[<title of the page that now holds the answer>]]` (in link fields, the plain title). Do not leave it with `status: resolved`, and do not set `resolves` on the decision: the question is gone, its text lives in the answer's context.
- **Still open**: leave the page as it is; if the user added something useful, put it under `## Known so far`.
- **No longer relevant**: delete the page and remove the links to it; the reason goes in the summary, not in the brain.

Answers that contradict an accepted decision or a source of truth are not written as they are: say what they contradict and ask which holds, as `/pb:fix` does for contested information.

## 4. Close

Closing flow of the writing conventions, once, with every file created, changed or deleted. Summarise in the user's language: questions answered (each with the page that now holds the answer, as a Markdown link to its repo path), left open, removed as no longer relevant.
