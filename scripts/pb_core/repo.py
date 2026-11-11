"""Git and GitHub helpers: the repository a brain lives in, its default branch, its GitHub name."""
import json
import os
import re
import subprocess
from pathlib import Path

from .errors import GitError, UsageError


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
