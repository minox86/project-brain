---
name: brief
description: Turns the project brain into a ready-to-use briefing for one role — QA test scenarios from a feature's expected behaviour, PM release notes from an epic, a designer's view of UX choices and constraints, a developer's technical briefing, or an onboarding tour of the product for a newcomer. Read-only; works in Claude Code and in Cowork. Use when someone asks for test cases, release notes, a design or dev briefing, or an introduction to the product ("what should QA test on FIN-412?", "draft release notes for the approval epic", "onboard me on this product").
argument-hint: "<qa | pm | design | dev | onboarding> [feature | epic | Jira key]"
---

# /pb:brief — a briefing for one role

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Works in repo mode and read mode. In Cowork without a GitHub connector that reads the monorepo, guide the user to connect it first (see **Connectors** in the conventions).

A brief is **derived** from the brain: show it in the conversation, never write it into `brain/` (it would fail the significance gate). The user may copy it into Jira, Confluence or a test tool.

## 1. Role and subject

- Role: the first argument, or infer it from the request (test cases → `qa`, release notes → `pm`, UX → `design`, "before I code" → `dev`, "new to the product" → `onboarding`). Still unclear: ask, offering the five roles.
- Subject: a feature or epic title, or a Jira key. `onboarding` needs none.

## 2. Gather

- **Repo mode:** `PB context --jira <KEY>` or `PB context --feature "<title>"` (resolve the title with `PB resolve` first). For `onboarding`: `brain/index.md`, `brain/glossary.md`, and `PB stats`.
- **Read mode:** `brain/context/<title>.md` from the default branch (for a Jira key, find the epic or feature page that lists it); for `onboarding`, `brain/index.md` and `brain/glossary.md`.
- Nothing found: say so and suggest the closest titles from the index. Never fill gaps from general knowledge: a brief contains only what the brain says, and says what is missing.

## 3. Write the brief

Cite brain pages as `[[Title]]` and keep each brief short: one screen if possible.

**qa** — test scenarios for the feature or epic.
- One scenario per rule, state and edge case in `## Expected behaviour` and in the epic's agreed scope: title, preconditions, steps, expected result.
- Negative cases from `## Out of scope` and from constraints.
- Use the glossary terms of the product.
- **Not yet testable**: open questions affecting the subject. **Gaps**: behaviour the brain does not describe.

**pm** — release notes for an epic (or a feature).
- What changes for users, in plain language, grouped as New / Changed / Removed. Take it from the epic's `## Outcome` or agreed scope and from the features it touches.
- Known limitations: `## Out of scope` and open questions.
- No internal module names; no person names.

**design** — UX briefing.
- User problem (feature `## Purpose`), current UX notes and Figma links.
- Accepted decisions with `area: ux`, as constraints.
- Open questions with `area: ux` or `functional`: what is still to design.
- Domain terms to use in the UI (glossary, both languages).

**dev** — technical briefing before starting work.
- Modules and interfaces involved, with the code paths from `module.paths`.
- Accepted technical decisions as constraints; epic constraints and risks.
- Open questions that could block the work.
- The context pack in short, then "read in full" pointers for long pages.

**onboarding** — a tour of the product, about 10 minutes of reading.
- What the product does, in 3–5 lines from the most connected features.
- The main features and the modules that implement them, one line each.
- The 10–15 glossary terms to know first, in both languages.
- The decisions that shape the product most, one line each.
- Epics in progress, and open questions worth knowing.
- Where to go next: `brain/index.md`, `/pb:ask`, `/pb:context`.

## 4. Close

End with one line naming the pages used, and offer the next step: another role for the same subject, or `/pb:ask` for follow-up questions.
