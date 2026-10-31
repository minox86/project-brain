---
name: context
description: Builds a context pack from the project brain for a Jira issue or epic, a feature or a set of code paths — the active epics, relevant features, concepts, modules, interfaces, accepted decisions and open questions — for an agent or a person about to work on it. Use when the user asks for context before working on a ticket, feature or files ("give me the context for FIN-412", "what should I know before touching services/billing?").
argument-hint: "<JIRA-KEY | feature or epic title | paths…>"
---

# /pb:context — context pack

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Works in repo mode and read mode. In Cowork without a GitHub connector that reads the monorepo, guide the user to connect it first (see **Connectors** in the conventions).

## Repo mode

1. Choose the seed: a Jira key (`ABC-123`) → `--jira` (it matches epic pages and features listing the key; for a story or task, first find its parent epic with `getJiraIssue` and use that key if the issue itself matches nothing; without the Atlassian connector, suggest connecting it or ask the user for the epic key); existing file or folder paths → `--paths`; otherwise → `--feature` with a feature or epic title (resolve it with `PB resolve` first). No argument: use the files changed on the current branch (`git diff --name-only $(git merge-base HEAD origin/HEAD)`).
2. `PB context <seed>`.
3. Empty result: say which seed found nothing; for paths, suggest creating or fixing the module's `paths` (`/pb:put` or `/pb:fix`).
4. Present `markdown` as is, then one line listing pages included as summary only (`included: "summary"`), which can be read in full on request.

## Read mode

For a feature or an active epic, read `brain/context/<title>.md` from the default branch. For a Jira key, find the epic page (`brain/epics/`) or feature whose `jira` field lists it. For paths, find modules whose `paths` cover them (module pages in `brain/technical/modules/`), then follow their links to interfaces, features, decisions (not superseded) and open questions (open only). Present the same sections: Epics, Features, Concepts, Modules, Interfaces, Decisions, Open questions.
