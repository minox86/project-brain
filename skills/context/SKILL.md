---
name: context
description: Builds a context pack from the project brain for a Jira issue, a feature or a set of code paths — the relevant features, concepts, modules, interfaces, accepted decisions and open questions — for an agent or a person about to work on it. Use when the user asks for context before working on a ticket, feature or files ("give me the context for FIN-412", "what should I know before touching services/billing?").
argument-hint: "<JIRA-KEY | feature title | paths…>"
---

# /pb:context — context pack

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Works in repo mode and read mode.

## Repo mode

1. Choose the seed: a Jira key (`ABC-123`) → `--jira`; existing file or folder paths → `--paths`; otherwise → `--feature` (resolve the title with `PB resolve` first). No argument: use the files changed on the current branch (`git diff --name-only $(git merge-base HEAD origin/HEAD)`).
2. `PB context <seed>`.
3. Empty result: say which seed found nothing; for paths, suggest creating or fixing the module's `paths` (`/pb:put` or `/pb:fix`).
4. Present `markdown` as is, then one line listing pages included as summary only (`included: "summary"`), which can be read in full on request.

## Read mode

For a feature, read `brain/context/<feature>.md` from the default branch. For a Jira key, find the feature whose `jira` field lists it (search the index, then the feature pages). For paths, find modules whose `paths` cover them (module pages in `brain/technical/modules/`), then follow their links to interfaces, features, decisions (not superseded) and open questions (open only). Present the same sections: Features, Concepts, Modules, Interfaces, Decisions, Open questions.
