# project-brain (`pb`)

A Claude plugin that keeps your product's knowledge (features, epics, domain concepts, modules, decisions, open questions) in a `brain/` folder of your monorepo, written for AI agents and readable by people. It works in Claude Code and Claude Cowork.

- **Developers** read and write the brain from Claude Code. Their changes go out with their PR.
- **PMs, designers, analysts, QA** read the brain from Cowork. What they write on Confluence and discuss in Teams reaches the brain through a nightly routine.

## Install

**Claude Code**

```
/plugin marketplace add minox86/project-brain
/plugin install pb@project-brain
```

**Cowork, on your own**

1. Open **Customize** in the sidebar, then **Plugins**.
2. Select **Add marketplace** and enter `minox86/project-brain`.
3. Find **pb** in the list and click **Install**.
4. Connect the **GitHub** connector with read access to your product monorepo: that is where Cowork reads the brain from.

**Cowork, for the whole team** (an Owner of the Claude organization)

Org marketplaces must be **private or internal** repositories on github.com. Fork or mirror this repo as a private repo in your GitHub organization. Then sync it from **Organization settings → Plugins** and make `pb` available, or required, for the product team. Cowork and Skills must be enabled for the organization.

## Set up (once per product)

**1. Create the brain** (a developer, in Claude Code; needs Python 3.9+ and git)

1. Open the monorepo and create a branch: `git switch -c pb/init`.
2. Run `/pb:init`. Claude looks at the repo, then asks you a few rounds of questions to shape the wiki around your product. Answer "yes" to accept its suggestion.
3. Confirm. Claude creates `brain/`, adds two GitHub workflows and proposes the first pages.
4. Open a PR and merge it.

In the monorepo's GitHub settings, set **Actions → General → Workflow permissions** to "Read and write" and turn on **General → Allow auto-merge**. If `main` is protected, allow GitHub Actions to push to it.

**2. Set up the nightly routine** (the Engineering Manager, in Claude Code)

1. Enable the Microsoft 365 and Atlassian connectors in your Claude account.
2. Run `/pb:routine-setup` and pick:
   - the Teams channels and Confluence spaces to read;
   - the Jira projects whose epics to follow;
   - the branch the routine writes to;
   - how often it runs: every night (default), weekdays only, a few times a day, every N hours, once a week, or a custom schedule. At most once an hour.
3. Claude creates the routine for you (or prints the steps to do it) and starts a first run.
4. Check `brain/digests/<today>.md`: it lists what was added and what was skipped.

## Use

### What happens on its own

Once the brain and the routine are set up, nobody needs to run a command for these:

- **Teams, Confluence and Jira flow in every night.** The routine reads the configured channels and spaces, the Jira epics and the merged PRs. It keeps only what is worth remembering (decisions, requirement clarifications, domain explanations, open questions), never copies messages verbatim, and writes a digest of what it added and skipped in `brain/digests/`.
- **Epics stay in sync.** Discussions that mention a Jira epic key are filed under that epic. When the epic is done in Jira, what still matters moves to the feature and decision pages and the epic shrinks to a short outcome.
- **Every Claude session in the monorepo knows the brain.** `CLAUDE.md` points to `brain/AGENTS.md`, so Claude Code reads it without the plugin installed. It uses the glossary terms, starts from the context of the feature or epic you are working on, follows accepted decisions, and tells you when the code contradicts the brain. Other AI agents that read `AGENTS.md`-style instructions can use it the same way.
- **The brain checks itself on every PR.** CI blocks brain changes with broken links, malformed pages or anything that looks like a password or token. PRs that touch only `brain/` merge on their own once the checks pass.
- **Indexes stay fresh.** After every merge (and at least hourly) CI rebuilds the index, the bilingual glossary and a ready-made context pack for every feature and every active epic in `brain/context/`.
- **Old items step aside.** Superseded decisions, answered questions and closed epics drop out of the index after a while; history stays in git.
- **You don't need the slash commands.** Plain requests work: "what did we decide about approvals?", "save this decision in the brain", "give me the context for FIN-412". In Cowork, asking a product question is enough.

### When you want to do something

**In Claude Code (developers)**

| You want to… | Say it, or run |
|---|---|
| Get context before a ticket | `/pb:context FIN-412` (or a feature, an epic, or file paths) |
| Ask something | `/pb:ask why do invoices have a single approver?` |
| Save what you learned in this session | `/pb:capture` |
| Add a document, Confluence page or Jira ticket | `/pb:put <file \| link \| jira:KEY \| text>` |
| Save a Teams meeting | `/pb:meeting last` |
| Correct something wrong | `/pb:fix <what is wrong and what is right>` |
| Clean up the brain | `/pb:lint --fix` |
| Run the routine now, without waiting for the night | `/pb:routine-run` (add `--local` to run it here with your connectors, `--check` to only preview) |
| Change how often the routine runs | `/pb:routine-setup schedule every 4 hours` |
| Change the wiki structure | `/pb:schema` |

Changes are committed on your current branch and go out with your PR.

**In Cowork (everyone)**

- Ask: `/pb:ask what is still open on multi-level approval?`
- Get a briefing: `/pb:context <feature, epic or Jira key>`

Cowork only reads the brain. To add knowledge, write where you already do: analyses on Confluence, discussions in the Teams channel. Mention the Jira epic key and the routine files the content under that epic.

## Troubleshooting

- **A connector is missing** (Atlassian, Microsoft 365, GitHub): the command tells you which one and how to connect it, and offers a workaround meanwhile. In Cowork, connectors live under **Customize → Connectors**; some may need an organization Owner to enable them.
- **Cowork says the brain is not reachable**: connect GitHub with read access to the monorepo.
- **Nothing was added overnight**: read "Problems" in the latest digest in `brain/digests/`.
- **Wrong information**: a developer runs `/pb:fix`. Anyone else can report it in the Teams channel.
- **After updating the plugin**: in the monorepo, ask Claude to run `pb toolkit-sync` and commit the result, so CI uses the new version.
