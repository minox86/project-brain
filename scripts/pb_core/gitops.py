"""Git operations: dev commits on the current branch, routine runs on docs/brain with one PR."""
import datetime
from pathlib import Path

from .brain import GENERATED, Brain
from .errors import GitError, UsageError
from .generate import generate
from .repo import (BRAIN_BRANCH, BRAIN_PR_TITLE, brain_pr_body, default_branch, ensure_brain_pr, gh_repo,
                   git as _git, request_reviewers)
from .retention import apply_retention
from .review import review


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


def adds_nothing(repo, branch, base):
    """True when merging origin/<branch> into origin/<base> would leave <base>'s tree unchanged: everything the
    branch holds is already on <base> (its PR was merged, by any method, squash included). False when the
    merge conflicts or git cannot tell (a missing ref, unrelated histories, git older than 2.38)."""
    merged = _git(repo, "merge-tree", "--write-tree", f"origin/{base}", f"origin/{branch}", check=False)
    tree = _git(repo, "rev-parse", "--verify", "--quiet", f"origin/{base}^{{tree}}", check=False)
    if merged.returncode != 0 or tree.returncode != 0:
        return False
    lines = merged.stdout.split()
    return bool(lines) and lines[0] == tree.stdout.strip()


def _behind(repo, branch, base):
    """How many commits of origin/<base> origin/<branch> lacks (0 when either is missing)."""
    proc = _git(repo, "rev-list", "--count", f"origin/{branch}..origin/{base}", check=False)
    return int(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip().isdigit() else 0


def _start_point(repo, branch):
    """Where the run starts: (ref, created, restarted, behind). The branch is restarted from the default branch,
    never merged with it, when it holds nothing the default branch lacks."""
    base = default_branch(repo)
    if not _remote_has(repo, branch):
        return (f"origin/{base}" if _remote_has(repo, base) else "HEAD"), True, False, 0
    if branch != base and adds_nothing(repo, branch, base):
        same = _git(repo, "rev-parse", f"origin/{branch}").stdout == _git(repo, "rev-parse", f"origin/{base}").stdout
        return f"origin/{base}", False, not same, 0
    return f"origin/{branch}", False, False, _behind(repo, branch, base)


def routine_start(repo, branch, worktree=None):
    """Needs only the clone: the brain lives on the branch, not necessarily in the current checkout."""
    repo = Path(repo)
    _git(repo, "fetch", "-q", "origin")
    start, created, restarted, behind = _start_point(repo, branch)
    out = {"branch": branch, "created": created, "restarted": restarted, "behind": behind}
    if worktree is not None:
        # Manual runs: a detached worktree, so the user's checkout is never touched.
        _git(repo, "worktree", "add", "-q", "--detach", str(worktree), start)
        worktree = Path(worktree).resolve()
        return dict(out, worktree=str(worktree), brain=str(worktree / "brain"))
    _git(repo, "checkout", "-q", "-B", branch, start)
    return out


def routine_cleanup(repo, worktree):
    repo = Path(repo)
    _git(repo, "worktree", "remove", "--force", str(worktree))
    _git(repo, "worktree", "prune")
    return {"removed": str(worktree)}


def routine_finish(brain, branch, message, confidence=()):
    """Apply retention, commit the run, regenerate and push it to `branch`; on docs/brain, keep the one PR towards
    the default branch open, with the watched changes in its description and the area reviewers requested.
    Never merges: a branch that moved on origin is pushed over only when it holds nothing the default branch lacks."""
    repo = _repo_root(brain)
    base = default_branch(repo)
    if branch == base:
        raise UsageError(f"the routine never pushes to the default branch '{base}': use --branch {BRAIN_BRANCH}")
    retention = apply_retention(brain, datetime.date.today())
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    done = commit(brain, message, allow_default=True)
    regenerate(brain.root, repo)
    _git(repo, "fetch", "-q", "origin")
    # Everything the PR holds, not only this run: the changes since the fork from the default branch.
    # Confidence levels are known for this run's pages only.
    fork = _git(repo, "merge-base", f"origin/{base}", "HEAD", check=False)
    routed = review(brain, fork.stdout.strip() if fork.returncode == 0 else before, confidence)
    out = {"committed": done["committed"], "pushed": False, "conflict": False, "pr": None,
           "watched": routed["review"], "reviewers": routed["reviewers"], "behind": 0,
           "retention": retention, "problems": []}
    push = ["push", "-q"]
    if _remote_has(repo, branch):
        tip = _git(repo, "rev-parse", f"origin/{branch}").stdout.strip()
        if _git(repo, "merge-base", "--is-ancestor", tip, "HEAD", check=False).returncode != 0:
            if not adds_nothing(repo, branch, base):
                out["conflict"] = True
                out["behind"] = _behind(repo, branch, base)
                return out
            push.append(f"--force-with-lease=refs/heads/{branch}:{tip}")  # a restart from the default branch
    if _git(repo, *push, "origin", f"HEAD:refs/heads/{branch}", check=False).returncode:
        out["conflict"] = True
        out["problems"].append(f"the push to {branch} was refused")
        out["behind"] = _behind(repo, branch, base)
        return out
    out["pushed"] = True
    out["behind"] = _behind(repo, branch, base)
    if branch == BRAIN_BRANCH and _ahead(repo, base):
        _brain_pr(brain, base, routed, out)
    return out


def _ahead(repo, base):
    """HEAD holds commits origin/<base> lacks (with none, GitHub refuses the PR)."""
    proc = _git(repo, "rev-list", "--count", f"origin/{base}..HEAD", check=False)
    return proc.returncode != 0 or proc.stdout.strip() != "0"


def _brain_pr(brain, base, routed, out):
    owner = gh_repo(brain)
    if not owner:
        out["problems"].append(f"no GitHub repo (github.repo in sources.md): the {BRAIN_PR_TITLE} PR from "
                               f"{BRAIN_BRANCH} to {base} was not opened")
        return
    url, number, problem = ensure_brain_pr(owner, base, brain_pr_body(routed["markdown"], out["behind"], base))
    out["pr"] = url
    if problem:
        out["problems"].append(problem)
    if number is not None:
        out["problems"] += request_reviewers(owner, number, routed["reviewers"])


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
