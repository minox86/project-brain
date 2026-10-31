"""Git operations: dev commits on the current branch, routine runs on a target branch."""
import subprocess
from pathlib import Path

from .brain import GENERATED
from .errors import GitError


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


def commit(brain, message, allow_default=False, include=()):
    repo = _repo_root(brain)
    branch = current_branch(repo)
    if not allow_default and branch == default_branch(repo):
        raise GitError(f"current branch '{branch}' is the default branch",
                       {"error": f"current branch '{branch}' is the default branch: switch to a working branch "
                                 "or pass --allow-default", "code": "on-default-branch", "branch": branch})
    prefix = _brain_prefix(brain, repo)
    specs = [prefix] + [f":(exclude){prefix}/{g.rstrip('/')}" for g in GENERATED] + list(include)
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


def routine_finish(brain, branch, message):
    repo = _repo_root(brain)
    done = commit(brain, message, allow_default=True)
    _git(repo, "fetch", "-q", "origin")
    if _remote_has(repo, branch):
        rebase = _git(repo, "rebase", "-q", f"origin/{branch}", check=False)
        if rebase.returncode != 0:
            _git(repo, "rebase", "--abort", check=False)
            return {"committed": done["committed"], "pushed": False, "conflict": True}
    _git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    return {"committed": done["committed"], "pushed": True, "conflict": False}


def routine_discard(brain):
    """Throw away every brain/ change of this run except the digests."""
    repo = _repo_root(brain)
    prefix = _brain_prefix(brain, repo)
    specs = [prefix, f":(exclude){prefix}/digests"]
    _git(repo, "reset", "-q", "--", *specs)
    _git(repo, "checkout", "--", *specs, check=False)
    _git(repo, "clean", "-fdq", "--", *specs)
    return {"discarded": True}
