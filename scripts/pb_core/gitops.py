"""Git operations: dev commits on the current branch, routine runs on a target branch."""
import datetime
import json
import re
import subprocess
from pathlib import Path

from .brain import GENERATED
from .errors import GitError
from .review import review
from .workspace import BRAIN_BRANCH, ensure_promotion, regenerate

REVIEW_PREFIX = "pb/review/"


def _git(cwd, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def _repo_root(brain):
    return Path(_git(brain.root, "rev-parse", "--show-toplevel").stdout.strip())


def _brain_prefix(brain, repo):
    return brain.root.resolve().relative_to(repo.resolve()).as_posix()


def current_branch(repo):
    return _git(repo, "branch", "--show-current").stdout.strip()


def default_branch(repo):
    proc = _git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().rsplit("refs/remotes/origin/", 1)[-1]
    for name in ("main", "master"):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False).returncode == 0:
            return name
    return "main"


def _staged(repo, specs):
    out = _git(repo, "-c", "core.quotePath=false", "diff", "--cached", "--name-only", "--no-renames", "-z",
               "--", *specs).stdout
    return [f for f in out.split("\0") if f]


def commit(brain, message, allow_default=False, include=(), exclude=()):
    repo = _repo_root(brain)
    branch = current_branch(repo)
    if not allow_default and branch == default_branch(repo):
        raise GitError(f"current branch '{branch}' is the default branch",
                       {"error": f"current branch '{branch}' is the default branch: switch to a working branch "
                                 "or pass --allow-default", "code": "on-default-branch", "branch": branch})
    prefix = _brain_prefix(brain, repo)
    specs = ([prefix] + [f":(exclude){prefix}/{g.rstrip('/')}" for g in GENERATED]
             + [f":(exclude){prefix}/{rel}" for rel in exclude] + list(include))
    _git(repo, "add", "-A", "--", *specs)
    files = _staged(repo, specs)
    if not files:
        return {"committed": False, "sha": None, "branch": branch, "files": []}
    _git(repo, "commit", "-q", "-m", message, "--", *specs)
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return {"committed": True, "sha": sha, "branch": branch, "files": files}


def _remote_has(repo, branch):
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", check=False).returncode == 0


def routine_start(brain, branch, worktree=None):
    repo = _repo_root(brain)
    _git(repo, "fetch", "-q", "origin")
    if worktree is not None:
        return _start_in_worktree(brain, repo, branch, Path(worktree))
    if _remote_has(repo, branch):
        _git(repo, "checkout", "-q", "-B", branch, f"origin/{branch}")
        return {"branch": branch, "created": False}
    base = default_branch(repo)
    start = f"origin/{base}" if _remote_has(repo, base) else "HEAD"
    _git(repo, "checkout", "-q", "-B", branch, start)
    return {"branch": branch, "created": True}


def _start_in_worktree(brain, repo, branch, worktree):
    """Manual runs: a detached worktree on the target branch, so the user's checkout is never touched."""
    created = not _remote_has(repo, branch)
    start = f"origin/{default_branch(repo) if created else branch}"
    _git(repo, "worktree", "add", "-q", "--detach", str(worktree), start)
    worktree = worktree.resolve()
    return {"branch": branch, "created": created, "worktree": str(worktree),
            "brain": str(worktree / _brain_prefix(brain, repo))}


def routine_cleanup(brain, worktree):
    repo = _repo_root(brain)
    _git(repo, "worktree", "remove", "--force", str(worktree))
    _git(repo, "worktree", "prune")
    return {"removed": str(worktree)}


def routine_finish(brain, branch, message, confidence=()):
    """Push the run to `branch`; changes the review policy holds back go to a PR on top of it instead."""
    repo = _repo_root(brain)
    routed = review(brain, "HEAD", confidence)
    held = [item["path"] for item in routed["review"]]
    done = commit(brain, message, allow_default=True, exclude=held)
    direct_tip = _git(repo, "rev-parse", "HEAD").stdout.strip()
    held_commit = None
    if held:
        prefix = _brain_prefix(brain, repo)
        specs = [f"{prefix}/{rel}" for rel in held]
        _git(repo, "add", "-A", "--", *specs)
        _git(repo, "commit", "-q", "-m", f"{message} (review)", "--", *specs)
        held_commit = _git(repo, "rev-parse", "HEAD").stdout.strip()
        _git(repo, "reset", "-q", "--keep", direct_tip)
    _git(repo, "fetch", "-q", "origin")
    if _remote_has(repo, branch):
        rebase = _git(repo, "rebase", "-q", f"origin/{branch}", check=False)
        if rebase.returncode != 0:
            _git(repo, "rebase", "--abort", check=False)
            return {"committed": done["committed"], "pushed": False, "conflict": True, "review": None}
    regenerate(brain.root, repo)
    _git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    result = {"committed": done["committed"], "pushed": True, "conflict": False, "review": None,
              "promotion": None, "problems": []}
    if held_commit:
        result["review"] = _open_review(brain, repo, branch, message, routed, held_commit)
    if branch == BRAIN_BRANCH and done["committed"]:
        owner = (brain.sources.get("github") or {}).get("repo") or _origin_repo(repo)
        result["promotion"], problem = ensure_promotion(repo, owner)
        if problem:
            result["problems"].append(problem)
    return result


def _open_review(brain, repo, branch, message, routed, held_commit):
    """Put the held changes on a pb/review/ branch off the pushed tip and open a PR with the area reviewers."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    head = f"{REVIEW_PREFIX}{stamp}"
    out = {"branch": head, "pages": [item["path"] for item in routed["review"]], "pr": None, "problems": []}
    back = current_branch(repo) or _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", "--detach")
    try:
        if _git(repo, "cherry-pick", held_commit, check=False).returncode != 0:
            _git(repo, "cherry-pick", "--abort", check=False)
            out["problems"].append(f"the held changes no longer apply on {branch}: they are dropped for this run")
            return out
        _git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{head}")
    finally:
        _git(repo, "checkout", "-q", back)
    gh_repo = (brain.sources.get("github") or {}).get("repo") or _origin_repo(repo)
    if not gh_repo:
        out["problems"].append(f"no GitHub repo (github.repo in sources.md): open a PR from {head} to {branch} by hand")
        return out
    body = routed["markdown"] + "\nOpened by the pb routine. Merge to accept, edit the pages here to correct them, " \
                                "close to drop them.\n"
    try:
        pr = _gh_json(["api", f"repos/{gh_repo}/pulls", "-X", "POST", "-f", f"title={message} (review)",
                       "-f", f"head={head}", "-f", f"base={branch}", "-f", f"body={body}"])
    except GitError as exc:
        out["problems"].append(f"PR not opened, open it by hand from {head} to {branch}: {exc}")
        return out
    out["pr"] = pr.get("html_url")
    people = routed["reviewers"]
    if people["users"] or people["teams"]:
        args = ["api", f"repos/{gh_repo}/pulls/{pr.get('number')}/requested_reviewers", "-X", "POST"]
        args += [x for u in people["users"] for x in ("-f", f"reviewers[]={u}")]
        args += [x for t in people["teams"] for x in ("-f", f"team_reviewers[]={t}")]
        try:
            _gh_json(args)
        except GitError as exc:
            out["problems"].append(f"reviewers not requested: {exc}")
    out["reviewers"] = people
    return out


def _gh_json(args):
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise GitError("the GitHub CLI (gh) is not installed")
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or proc.stdout.strip() or "gh failed")
    return json.loads(proc.stdout or "null") or {}


def _origin_repo(repo):
    url = _git(repo, "remote", "get-url", "origin", check=False).stdout.strip()
    found = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return found.group(1) if found else None


def routine_discard(brain):
    """Throw away every brain/ change of this run except the digests."""
    repo = _repo_root(brain)
    prefix = _brain_prefix(brain, repo)
    specs = [prefix, f":(exclude){prefix}/digests"]
    _git(repo, "reset", "-q", "--", *specs)
    _git(repo, "checkout", "--", *specs, check=False)
    _git(repo, "clean", "-fdq", "--", *specs)
    return {"discarded": True}
