---
name: setup
description: Prepares a developer's computer to read and write the project brain from Claude Code — checks and installs git, Python and the GitHub CLI, signs in to GitHub, sets the git identity, clones the product monorepo, quiets permission prompts and proves the chain with a first read. Use when someone joins the team, when a pb skill says the environment is not ready (no clone, no gh, not logged in), or when the user asks to set up, install or configure pb on their machine.
argument-hint: "[owner/repo]"
---

# /pb:setup — get ready to use the brain

Arguments: `$ARGUMENTS`

Read `BASE/../../references/conventions.md`. Plain words, one step at a time. Idempotent: every step checks first and only fixes what is missing; rerunning it is safe.

Ask every choice with the **`AskUserQuestion` tool** (recommended option first, labelled "(Recommended)"); in text only if the tool is not available. Run what you can run yourself. When something needs the user (a password, a browser page, an admin), say exactly what to do and give commands to type as `! <command>` lines (the `!` runs them in this session).

## 1. Tools

Check `git --version`, `python3 --version` (3.9 or later) and `gh --version`. For what is missing, by platform (`uname -s`):
- **macOS**: git and Python come with the Command Line Tools: `! xcode-select --install`, then wait for the installer window to finish. `gh`: `brew install gh` when Homebrew is there (`brew --version`), otherwise the installer from https://cli.github.com.
- **Windows**: `winget install --id Git.Git`, `winget install --id Python.Python.3.12`, `winget install --id GitHub.cli`; then a new Claude Code session so the new commands are found.
- **Linux**: the distribution's package manager (`apt install git python3 gh`, or the GitHub CLI repository instructions).

Check again after installing. Do not go on until all three answer.

## 2. GitHub sign-in

`gh auth status`. If not signed in: `! gh auth login --web --git-protocol https`. The user copies the one-time code into the browser page that opens and approves. Then `gh auth setup-git`, so git uses the same sign-in, and check `gh auth status` again.

## 3. Git identity

`git config --global user.name` and `user.email`. If either is empty, propose them from the GitHub account (`gh api user` → `name`, and `email` or `<id>+<login>@users.noreply.github.com`) and set them with the user's confirmation.

## 4. The monorepo

- Already inside a clone (`git rev-parse --show-toplevel`)? Use it.
- Otherwise find the repo: the argument, or ask (`AskUserQuestion` with the repos of the user's organisations that look like the product, from `gh repo list <org> --limit 50`). Propose a folder (`~/Projects/<name>` on macOS and Linux, `%USERPROFILE%\Projects\<name>` on Windows) and clone it there: `gh repo clone <owner/repo> <folder>`.
- Tell the user how to open that folder in Claude Code (desktop app: **Open folder**; terminal: `cd <folder> && claude`), and that the next steps must run from there. If this session is not in the clone, stop here with that instruction: rerunning `/pb:setup` there finishes the job.

## 5. Permissions on the repo

`gh api repos/<owner/repo> --jq .permissions`. `push: true` is required: brain pages travel in the user's branches and PRs, and `/pb:sync`, `/pb:routine-run --local` and `/pb:merge` push the branch `docs/brain`. If it is false, stop and give the exact request for a repo admin: "Please give <login> write access to <owner/repo>". Write access does not let anyone change protected branches: code still needs approved PRs. Fork-based contributions are not supported.

## 6. Quiet operation

So that the user is not asked to approve every internal step, propose (show the rules, then ask) adding to the clone's **local** Claude Code settings, `.claude/settings.local.json` (never committed), merged with what is there:

```json
{"permissions": {"allow": [
  "Bash(python3 */scripts/pb.py *)",
  "Bash(gh auth status)",
  "Bash(gh api user)",
  "Bash(gh pr checks *)",
  "Bash(git rev-parse *)",
  "Bash(git fetch *)"
]}}
```

The pattern survives plugin upgrades (the plugin's folder changes with its version) and matches how the skills call the toolkit (see **Toolkit** in the conventions). The toolkit runs git and `gh` itself, so these cover the everyday flow; anything else still asks.

Also check that the `pb` plugin is enabled for this clone: the monorepo's `.claude/settings.json` lists `pb@project-brain` in `enabledPlugins` (written by `/pb:init`). If it is missing, the plugin keeps working for this user since they installed it; for newcomers, a maintainer adds `"enabledPlugins": {"pb@project-brain": true}` and the `project-brain` marketplace to that file in a normal code PR.

## 7. First read

`PB version`.
- `brain: null`: as **Modes** in the conventions says (a branch cut before the brain arrived, or no brain yet: a maintainer runs `/pb:init`).
- Otherwise run `PB stats` and show the product name (`brain/README.md`) and how many pages it has (`pages`).

## 8. Done

One short message: what was installed or changed, where the clone is, and what to try now: "ask the brain something" (`/pb:ask`), "give me the context of FIN-123" (`/pb:context`), "save this decision in the brain" (`/pb:put`). Pages they write stay in their working branch and reach the default branch with their code PR.
