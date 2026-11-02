"""Git operations: dev commits on the current branch, routine runs on a target branch."""
import datetime
from pathlib import Path

from .brain import GENERATED
from .errors import GitError
from .review import review
from .workspace import (BRAIN_BRANCH, REVIEW_PREFIX, _git, _remote_has, default_branch, ensure_promotion,
                        open_review_pr, origin_repo, regenerate)


def _repo_root(brain):
    return Path(_git(brain.root, "rev-parse", "--show-toplevel").stdout.strip())


def _brain_prefix(brain, repo):
    return brain.root.resolve().relative_to(repo.resolve()).as_posix()


def current_branch(repo):
    return _git(repo, "branch", "--show-current").stdout.strip()


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
    include = [p for p in include if (repo / p).exists()
               or _git(repo, "ls-files", "--error-unmatch", "--", p, check=False).returncode == 0]
    specs = ([prefix] + [f":(exclude){prefix}/{g.rstrip('/')}" for g in GENERATED]
             + [f":(exclude){prefix}/{rel}" for rel in exclude] + list(include))
    _git(repo, "add", "-A", "--", *specs)
    files = _staged(repo, specs)
    if not files:
        return {"committed": False, "sha": None, "branch": branch, "files": []}
    _git(repo, "commit", "-q", "-m", message, "--", *specs)
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return {"committed": True, "sha": sha, "branch": branch, "files": files}


def routine_start(repo, branch, worktree=None):
    """Needs only the clone: the brain lives on the branch, not necessarily in the current checkout."""
    repo = Path(repo)
    _git(repo, "fetch", "-q", "origin")
    if worktree is not None:
        return _start_in_worktree(repo, branch, Path(worktree))
    if _remote_has(repo, branch):
        _git(repo, "checkout", "-q", "-B", branch, f"origin/{branch}")
        return {"branch": branch, "created": False}
    base = default_branch(repo)
    start = f"origin/{base}" if _remote_has(repo, base) else "HEAD"
    _git(repo, "checkout", "-q", "-B", branch, start)
    return {"branch": branch, "created": True}


def _start_in_worktree(repo, branch, worktree):
    """Manual runs: a detached worktree on the target branch, so the user's checkout is never touched."""
    created = not _remote_has(repo, branch)
    start = f"origin/{default_branch(repo) if created else branch}"
    _git(repo, "worktree", "add", "-q", "--detach", str(worktree), start)
    worktree = worktree.resolve()
    return {"branch": branch, "created": created, "worktree": str(worktree),
            "brain": str(worktree / "brain")}


def routine_cleanup(repo, worktree):
    repo = Path(repo)
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
            return {"committed": done["committed"], "pushed": False, "conflict": True, "review": None,
                    "promotion": None, "problems": []}
    regenerate(brain.root, repo)
    if _git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{branch}", check=False).returncode:
        return {"committed": done["committed"], "pushed": False, "conflict": True, "review": None,
                "promotion": None, "problems": [f"the push to {branch} was refused (someone pushed meanwhile?)"]}
    result = {"committed": done["committed"], "pushed": True, "conflict": False, "review": None,
              "promotion": None, "problems": []}
    if held_commit:
        result["review"] = _open_review(brain, repo, branch, message, routed, held_commit)
    if branch == BRAIN_BRANCH and done["committed"]:
        result["promotion"], problem = ensure_promotion(repo, _owner(brain, repo))
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
    body = routed["markdown"] + "\nOpened by the pb routine. Merge to accept, edit the pages here to correct them, " \
                                "close to drop them.\n"
    out["pr"], problems = open_review_pr(_owner(brain, repo), head, f"{message} (review)", body, routed["reviewers"],
                                         base=branch)
    out["problems"] += problems
    out["reviewers"] = routed["reviewers"]
    return out


def _owner(brain, repo):
    return (brain.sources.get("github") or {}).get("repo") or origin_repo(repo)


def routine_discard(brain):
    """Throw away every brain/ change of this run except the digests."""
    repo = _repo_root(brain)
    prefix = _brain_prefix(brain, repo)
    specs = [prefix, f":(exclude){prefix}/digests"]
    _git(repo, "reset", "-q", "--", *specs)
    _git(repo, "checkout", "--", *specs, check=False)
    _git(repo, "clean", "-fdq", "--", *specs)
    return {"discarded": True}
