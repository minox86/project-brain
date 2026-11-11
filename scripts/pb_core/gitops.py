"""Git operations: dev commits on the current branch, routine runs on a target branch."""
from pathlib import Path

from .brain import GENERATED, Brain
from .errors import GitError
from .generate import generate
from .repo import default_branch, git as _git


def _repo_root(brain):
    return Path(_git(brain.root, "rev-parse", "--show-toplevel").stdout.strip())


def _brain_prefix(brain, repo):
    return brain.root.resolve().relative_to(repo.resolve()).as_posix()


def _remote_has(repo, branch):
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}",
                check=False).returncode == 0


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
    """Commit the run and push it to `branch`."""
    repo = _repo_root(brain)
    done = commit(brain, message, allow_default=True)
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
    return {"committed": done["committed"], "pushed": True, "conflict": False, "review": None,
            "promotion": None, "problems": []}


def regenerate(brain_root, repo):
    """Refresh index, glossary, context packs and backlinks from the committed pages; commit them if they changed.
    Runs after the rebase on the latest branch, so generated files never conflict."""
    done = generate(Brain(brain_root))
    prefix = Path(brain_root).resolve().relative_to(Path(repo).resolve()).as_posix()
    specs = [f"{prefix}/{g.rstrip('/')}" for g in GENERATED] + [f"{prefix}/{d}" for d in done["deleted"]]
    specs = [spec for spec in specs if (Path(repo) / spec).exists()
             or _git(repo, "cat-file", "-e", f"HEAD:{spec}", check=False).returncode == 0]
    if not specs:
        return False
    _git(repo, "add", "-A", "--", *specs)
    if _git(repo, "diff", "--cached", "--quiet", "--", *specs, check=False).returncode == 0:
        return False
    _git(repo, "commit", "-q", "-m", "pb(generate): refresh generated files", "--", *specs)
    return True


def routine_discard(brain):
    """Throw away every brain/ change of this run except the digests."""
    repo = _repo_root(brain)
    prefix = _brain_prefix(brain, repo)
    specs = [prefix, f":(exclude){prefix}/digests"]
    _git(repo, "reset", "-q", "--", *specs)
    _git(repo, "checkout", "--", *specs, check=False)
    _git(repo, "clean", "-fdq", "--", *specs)
    return {"discarded": True}
