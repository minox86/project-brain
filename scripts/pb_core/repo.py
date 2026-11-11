"""Git and GitHub helpers: the repository a brain lives in, its default branch, its GitHub name, the brain PR."""
import json
import os
import re
import subprocess
from pathlib import Path

from .errors import GitError, UsageError

BRAIN_BRANCH = "docs/brain"
BRAIN_PR_TITLE = "Brain updates"


def git(cwd, *args, check=True, env=None):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=dict(os.environ, **(env or {})))
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def default_branch(repo):
    proc = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().rsplit("refs/remotes/origin/", 1)[-1]
    for name in ("main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False).returncode == 0:
            return name
    return "main"


def origin_repo(repo):
    """owner/name from a GitHub origin URL, or None."""
    url = git(repo, "remote", "get-url", "origin", check=False).stdout.strip()
    found = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return found.group(1) if found else None


def repo_root(start):
    proc = git(start, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise UsageError("not inside a git repository: open the monorepo (run /pb:setup to clone it)")
    return Path(proc.stdout.strip())


def gh_json(args):
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        out = json.loads(proc.stdout or "null")
    except ValueError:
        return None
    return out if out is not None else {}


def gh_repo(brain):
    """owner/name of the monorepo: github.repo in the brain's sources.md, else the origin URL."""
    github = (brain.sources or {}).get("github")
    if isinstance(github, dict) and github.get("repo"):
        return github["repo"]
    return origin_repo(brain.repo_root)



def brain_pr_body(markdown, behind, base):
    """The description of the Brain updates PR: the behind notice, then the watched changes the PR holds."""
    lines = [f"Brain pages the pb routine wrote on `{BRAIN_BRANCH}`. Merging this PR brings them to `{base}`; "
             "edit the pages here to correct them.", ""]
    if behind:
        lines += [f"> `{BRAIN_BRANCH}` is behind `{base}`: run `/pb:merge` to bring these changes to `{base}` "
                  f"({behind} commit{'s' if behind != 1 else ''} of `{base}` are not on `{BRAIN_BRANCH}`).", ""]
    lines.append(markdown.rstrip("\n") if markdown.strip() else
                 "This PR holds nothing on a watched point and nothing of low confidence.")
    return "\n".join(lines) + "\n"


def ensure_brain_pr(owner, base, body):
    """The open PR docs/brain -> base, found (its body refreshed) or opened. Returns (url, number, problem, author),
    author the PR's `user.login` (None when unknown). gh api, not gh pr: cloud routines can only reach the REST API."""
    found = gh_json(["api", f"repos/{owner}/pulls?head={owner.split('/')[0]}:{BRAIN_BRANCH}&base={base}&state=open"])
    if found is None:
        return None, None, f"GitHub could not be reached (gh): the {BRAIN_PR_TITLE} PR was not checked", None
    if isinstance(found, list) and found:
        pr = found[0]
        number = pr.get("number")
        problem = None
        if gh_json(["api", f"repos/{owner}/pulls/{number}", "-X", "PATCH", "-f", f"body={body}"]) is None:
            problem = f"the description of the {BRAIN_PR_TITLE} PR could not be updated"
        return pr.get("html_url"), number, problem, _author(pr)
    pr = gh_json(["api", f"repos/{owner}/pulls", "-X", "POST", "-f", f"title={BRAIN_PR_TITLE}",
                  "-f", f"head={BRAIN_BRANCH}", "-f", f"base={base}", "-f", f"body={body}"])
    if not pr:
        return None, None, (f"the {BRAIN_PR_TITLE} PR could not be opened: it is retried at the next run "
                            f"(or open it by hand from {BRAIN_BRANCH} to {base})"), None
    return pr.get("html_url"), pr.get("number"), None, _author(pr)


def _author(pr):
    return ((pr.get("user") if isinstance(pr, dict) else None) or {}).get("login")


def request_reviewers(owner, number, reviewers, exclude=()):
    """Ask the area reviewers (users and team slugs) to review PR `number`, except the users in `exclude` (the PR's
    author: GitHub refuses the whole request when it is listed). Returns the problems."""
    skip = {e.lower() for e in exclude if e}
    users = [u for u in (reviewers or {}).get("users") or [] if u.lower() not in skip]
    teams = (reviewers or {}).get("teams") or []
    if not users and not teams:
        return []
    args = ["api", f"repos/{owner}/pulls/{number}/requested_reviewers", "-X", "POST"]
    args += [x for u in users for x in ("-f", f"reviewers[]={u}")]
    args += [x for t in teams for x in ("-f", f"team_reviewers[]={t}")]
    if gh_json(args) is None:
        return [f"reviewers not requested on the {BRAIN_PR_TITLE} PR: {', '.join(users + teams)}"]
    return []
