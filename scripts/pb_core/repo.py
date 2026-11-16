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


GITHUB = "github.com"
# `[scheme://][user@]host[:port](/|:)owner/name[.git]`: https, ssh and scp-like remotes, on github.com or on a
# GitHub Enterprise host. A local path is not one.
REMOTE = re.compile(r"^(?:[a-z][a-z0-9+.-]*://)?(?:[^@/\s]+@)?([^:/\s@]+)(?::\d+)?[:/]([^/\s:]+/[^/\s]+?)(?:\.git)?/?$",
                    re.IGNORECASE)
# The GitHub Enterprise host of this run (None: github.com, or whatever gh is set up for). Set once per command.
_host = None


def origin_parts(repo):
    """(host, owner/name) from the origin URL, or (None, None)."""
    url = git(repo, "remote", "get-url", "origin", check=False).stdout.strip()
    found = REMOTE.match(url)
    if not found or found.group(1).startswith(".") or (len(found.group(1)) == 1 and "://" not in url):
        return None, None  # a relative path, or a Windows drive
    return found.group(1).lower(), found.group(2)


def origin_repo(repo):
    """owner/name from the origin URL (github.com or a GitHub Enterprise host), or None."""
    return origin_parts(repo)[1]


def use_host(host):
    """The GitHub host every gh call of this command goes to: a GitHub Enterprise host, or None for gh's own
    default (github.com, or $GH_HOST when the user set it)."""
    global _host
    host = (host or "").strip().lower() or None
    if host:
        host = re.sub(r"^[a-z]+://", "", host).split("/")[0]
    _host = None if host in (None, GITHUB) else host
    return _host


def gh_host():
    return _host


def gh_command(args):
    """The gh command line for `args` (`api …`): `gh api` goes to github.com unless told the host, whatever the
    repo it runs in."""
    args = list(args)
    if _host and args[:1] == ["api"] and "--hostname" not in args and not os.environ.get("GH_HOST"):
        args[1:1] = ["--hostname", _host]
    return ["gh", *args]


def repo_root(start):
    proc = git(start, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise UsageError("not inside a git repository: open the monorepo (run /pb:setup to clone it)")
    return Path(proc.stdout.strip())


def gh_json(args):
    try:
        proc = subprocess.run(gh_command(args), capture_output=True, text=True)
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



def brain_pr_body(markdown, behind, base, waiting=""):
    """The description of the Brain updates PR: the behind notice, what waits for a decision (the review's queue),
    then the watched changes the PR holds."""
    lines = [f"Brain pages the pb routine wrote on `{BRAIN_BRANCH}`. Merging this PR brings them to `{base}`; "
             "edit the pages here to correct them.", ""]
    if behind:
        lines += [f"> `{BRAIN_BRANCH}` is behind `{base}`: run `/pb:merge` to bring these changes to `{base}` "
                  f"({behind} commit{'s' if behind != 1 else ''} of `{base}` are not on `{BRAIN_BRANCH}`).", ""]
    if waiting:
        lines += [waiting, ""]
    lines.append(markdown.rstrip("\n") if markdown.strip() else
                 "This PR holds nothing on a watched point and nothing of low confidence.")
    return "\n".join(lines) + "\n"


def ensure_brain_pr(owner, base, body, title=BRAIN_PR_TITLE):
    """The open PR docs/brain -> base, found (its body refreshed) or opened. Returns (url, number, problem, author),
    author the PR's `user.login` (None when unknown). The PR is found by head and base; `title` (pr_title_brain) is
    set on it, opened or found, so a changed format reaches the open PR. gh api, not gh pr: cloud routines can only reach the REST API."""
    found = gh_json(["api", f"repos/{owner}/pulls?head={owner.split('/')[0]}:{BRAIN_BRANCH}&base={base}&state=open"])
    if found is None:
        return None, None, "GitHub could not be reached (gh): the brain PR was not checked", None
    if isinstance(found, list) and found:
        pr = found[0]
        number = pr.get("number")
        problem = None
        if gh_json(["api", f"repos/{owner}/pulls/{number}", "-X", "PATCH", "-f", f"title={title}",
                    "-f", f"body={body}"]) is None:
            problem = "the title and description of the brain PR could not be updated"
        return pr.get("html_url"), number, problem, _author(pr)
    pr = gh_json(["api", f"repos/{owner}/pulls", "-X", "POST", "-f", f"title={title}",
                  "-f", f"head={BRAIN_BRANCH}", "-f", f"base={base}", "-f", f"body={body}"])
    if not pr:
        return None, None, ("the brain PR could not be opened: it is retried at the next run "
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
        return [f"reviewers not requested on the brain PR: {', '.join(users + teams)}"]
    return []
