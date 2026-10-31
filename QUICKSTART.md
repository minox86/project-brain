# project-brain — quick start

`pb` keeps a wiki of your product (features, epics, concepts, modules, decisions, open questions) in the `brain/` folder of your monorepo. Developers write to it from Claude Code. Everyone else reads it from Cowork. Every night a routine feeds it from Teams, Confluence and Jira.

## 1. Install the plugin (once per person)

**Claude Code**

```
/plugin marketplace add <org>/project-brain
/plugin install pb@project-brain
```

**Cowork**: nothing to do. The org admin adds this repo as a marketplace (Organization settings → Plugins & skills) and enables `pb` for the team. Then connect **GitHub** (read access to the monorepo) in Cowork.

## 2. Create the brain (once per product, one developer)

Requirements: Python 3.9+ and git.

1. Open the monorepo in Claude Code and create a branch: `git switch -c pb/init`.
2. Run `/pb:init`. Claude scans the repo, then asks you a few rounds of questions to tailor the schema. Answer "yes" to accept a recommendation.
3. Confirm the final schema. Claude then:
   - creates `brain/`;
   - adds two GitHub workflows;
   - adds a pointer in `CLAUDE.md`;
   - proposes a first set of pages.
4. Open a PR and merge it.

In the monorepo's GitHub settings:
- **Actions → General → Workflow permissions**: "Read and write".
- **General → Allow auto-merge**: on. PRs that touch only `brain/` then merge on their own once validated.
- If `main` is protected, let GitHub Actions push to it, or the index and context packs won't refresh.

## 3. Set up the nightly routine (once, Engineering Manager)

1. Make sure the Microsoft 365 and Atlassian connectors are enabled in your Claude account.
2. In the monorepo, run `/pb:routine-setup` and choose:
   - the Teams channels and Confluence spaces to read;
   - the Jira projects whose epics to follow;
   - the branch the routine pushes to (`main`, or a branch like `brain/inbox` that you merge yourself).
3. Merge the configuration, then follow the printed steps: `/schedule`, paste the prompt, then **Run now**.
4. Check `brain/digests/<today>.md` on the target branch: it lists what was ingested and what was skipped.

## 4. Daily use

**Developers (Claude Code)**

| You want to… | Run |
|---|---|
| Get context before a ticket | `/pb:context FIN-412` (or a feature, an epic, or file paths) |
| Ask something | `/pb:ask why do invoices have a single approver?` |
| Save what you learned in this session | `/pb:capture` (at the end of a task) |
| Add a document, page or ticket | `/pb:put <file \| Confluence link \| jira:KEY \| text>` |
| Save a Teams meeting | `/pb:meeting last` |
| Correct something wrong | `/pb:fix <what is wrong and what is right>` |
| Tidy up | `/pb:lint --fix` |

Brain changes are committed on your current branch and go out with your PR. You can also just ask in plain words ("save this decision in the brain").

**PMs, designers, analysts, QA (Cowork)**

- Ask questions: `/pb:ask what is still open on multi-level approval?`
- Get a briefing: `/pb:context <feature, epic or Jira key>`

The brain is read-only from Cowork. To add knowledge, write it where you already do: your analyses on Confluence, your discussions in the Teams channel. Mention the Jira epic key and the routine files it under that epic.

## 5. Something is off?

- **"The brain is not reachable"** (Cowork): connect GitHub with read access to the monorepo.
- **Nothing was ingested overnight**: read the "Problems" section of the latest digest in `brain/digests/`.
- **Wrong information**: a developer runs `/pb:fix`. Anyone else reports it in the Teams channel and the routine picks it up.
