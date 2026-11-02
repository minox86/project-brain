"""The managed brain copy: every pb read and write happens here, never in the user's checkout.

The brain always lives on the `docs/brain` branch. The copy is a worktree in the clone's git dir
(`<git-common-dir>/pb/brain-worktree`), detached on `origin/docs/brain`. A save commits there, rebases on the
latest brain and pushes straight to `docs/brain`; pages the review policy holds go to a `pb/review/` PR towards
`docs/brain`. One PR from `docs/brain` to the default branch, kept open, carries the brain to the code.
Commits that could not be pushed stay in the copy and go out with the next save.
"""
import contextlib
import datetime
import json
import os
import subprocess
import time
from pathlib import Path

from .errors import GitError, UsageError

BRAIN_BRANCH = "docs/brain"
REVIEW_PREFIX = "pb/review/"
LOCK_STALE_SECONDS = 600
PUSH_ATTEMPTS = 3
PROMOTION_TITLE = "Brain updates"
PROMOTION_BODY = (
    "Pages saved to the project brain on `docs/brain`. This PR stays open and gathers the next saves: merge it "
    "when the code branches should carry them (any merge method: `pb-brain-branch` brings the merge back into "
    "`docs/brain`).\n\nOpened by pb.\n")


def _git(cwd, *args, check=True, env=None):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env=dict(os.environ, **(env or {})))
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def repo_root(start):
    proc = _git(start, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise UsageError("not inside a git repository: open the monorepo (run /pb:setup to clone it)")
    return Path(proc.stdout.strip())


def pb_dir(repo):
    common = Path(_git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = (Path(repo) / common).resolve()
    return common / "pb"


def worktree_path(repo):
    return pb_dir(repo) / "brain-worktree"


def _alive(pid):
    try:
        os.kill(int(pid), 0)
    except (ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


@contextlib.contextmanager
def locked(repo):
    """One pb operation per clone at a time. A lock whose process is gone, or older than LOCK_STALE_SECONDS,
    is taken over; only the lock's own holder removes it."""
    folder = pb_dir(repo)
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / "lock"
    mine = str(os.getpid())
    message = "another Claude session is working on the brain of this clone: retry in a moment"
    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                holder = lock.read_text().strip()
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            # An empty lock is being written by its holder right now.
            if (_alive(holder) or (not holder and age < 5)) and age < LOCK_STALE_SECONDS:
                raise GitError(message, {"error": message, "code": "busy"})
            with contextlib.suppress(FileNotFoundError):
                lock.unlink()
    else:
        raise GitError(message, {"error": message, "code": "busy"})
    os.write(fd, mine.encode())
    os.close(fd)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            if lock.read_text().strip() == mine:
                lock.unlink()


def _remote_has(repo, branch):
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}",
                check=False).returncode == 0


def _fetch(repo):
    return _git(repo, "fetch", "-q", "--prune", "origin", check=False).returncode == 0


def _state(wt):
    """Uncommitted brain files, whether a rebase is stopped, and how many commits are not pushed yet."""
    status = _git(wt, "-c", "core.quotePath=false", "status", "--porcelain", "--untracked-files=all", "--",
                  "brain").stdout
    leftovers = sorted(path for path in (line[3:].split(" -> ")[-1].strip('"') for line in status.splitlines()
                                         if line.strip()) if not _generated(path))
    git_dir = Path(_git(wt, "rev-parse", "--absolute-git-dir").stdout.strip())
    rebasing = (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()
    unpushed = 0
    if not rebasing:
        out = _git(wt, "rev-list", "--count", f"origin/{BRAIN_BRANCH}..HEAD", check=False).stdout.strip()
        unpushed = int(out or 0)
    return leftovers, rebasing, unpushed


def _generated(path):
    from .brain import GENERATED
    rel = path[len("brain/"):] if path.startswith("brain/") else path
    return any(rel == g or (g.endswith("/") and rel.startswith(g)) for g in GENERATED)


def _no_brain():
    message = f"the brain branch '{BRAIN_BRANCH}' does not exist on origin: create the brain with /pb:init"
    return UsageError(message, {"error": message, "code": "no-brain", "branch": BRAIN_BRANCH})


def sync(repo):
    with locked(repo):
        return _sync(Path(repo))


def _sync(repo):
    online = _fetch(repo)
    if not _remote_has(repo, BRAIN_BRANCH):
        if not online:
            message = "GitHub cannot be reached from this computer: check the connection and retry"
            raise GitError(message, {"error": message, "code": "offline"})
        raise _no_brain()
    wt = worktree_path(repo)
    created = False
    if not (wt / ".git").exists():
        _git(repo, "worktree", "prune", check=False)
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-q", "--detach", str(wt), f"origin/{BRAIN_BRANCH}")
        created = True
    leftovers, rebasing, unpushed = _state(wt)
    if not rebasing:
        _unpark(repo, wt)
        leftovers, _, _ = _state(wt)
    if not leftovers and not rebasing:
        if unpushed:
            # Saved but not pushed yet: keep those commits, replayed on the latest brain.
            if _git(wt, "rebase", "-q", f"origin/{BRAIN_BRANCH}", check=False,
                    env={"GIT_EDITOR": "true"}).returncode:
                _git(wt, "rebase", "--abort", check=False)
        else:
            _git(wt, "checkout", "-q", "--detach", "-f", f"origin/{BRAIN_BRANCH}")
        leftovers, rebasing, unpushed = _state(wt)
    return {"worktree": str(wt), "brain": str(wt / "brain"), "branch": BRAIN_BRANCH, "created": created,
            "online": online, "leftovers": leftovers, "rebase_in_progress": rebasing, "unpushed": unpushed}


# --- saving -------------------------------------------------------------------------------------------------

FORCED_NOTE = "Configuration or toolkit change: always reviewed by a person (policy of the pb toolkit).\n"
ALWAYS_REVIEWED = ("brain/schema/", "brain/.pb/toolkit/")


def _brain_of(repo):
    from .brain import Brain
    wt = worktree_path(repo)
    if not (wt / ".git").exists():
        raise UsageError("the managed brain copy does not exist: run `PB workspace sync` first")
    return Brain(wt / "brain"), wt


def _fresh(wt):
    from .brain import Brain
    return Brain(wt / "brain")


def _pending_path(repo):
    return pb_dir(repo) / "pending.json"


def _read_pending(repo):
    path = _pending_path(repo)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _write_pending(repo, data):
    _pending_path(repo).write_text(json.dumps(data), encoding="utf-8")


def _clear_pending(repo):
    with contextlib.suppress(FileNotFoundError):
        _pending_path(repo).unlink()


def _result(**extra):
    out = {"saved": False, "committed": False, "pushed": False, "conflict": None, "errors": [],
           "review": None, "promotion": None, "unpushed": 0, "problems": []}
    out.update(extra)
    return out


def _check(brain, wt, files):
    """Validation errors on the pages touched by this save (other pages' problems never block it)."""
    from .validate import validate
    pages = [str(wt / f) for f in files if f.startswith("brain/") and f.endswith(".md") and (wt / f).is_file()]
    if not pages:
        return []
    return validate(brain, pages, "HEAD")["errors"]


def _head(wt):
    return _git(wt, "rev-parse", "HEAD").stdout.strip()


def _held_on_top(wt, pending):
    subject = _git(wt, "log", "-1", "--format=%s", check=False).stdout.strip()
    return bool(pending.get("held")) and subject == f"{pending['message']} (review)"


def _as_worktree_path(wt, raw):
    path = Path(raw)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(wt.resolve()).as_posix()
        except ValueError:
            return path.as_posix()
    rel = path.as_posix()
    return rel if rel.startswith("brain/") else f"brain/{rel}"


def _commit_paths(wt, message, files):
    _git(wt, "add", "-A", "--", *files)
    if _git(wt, "diff", "--cached", "--quiet", "--", *files, check=False).returncode == 0:
        return False
    _git(wt, "commit", "-q", "-m", message, "--", *files)
    return True


# Drafts: brain files in the copy that are not part of the save running now (another session's pages, or pages
# the user did not confirm). They are parked outside the worktree while it rebases and pushes, then put back.

def _parked(repo):
    return pb_dir(repo) / "parked"


def _park(repo, wt):
    leftovers, _, _ = _state(wt)
    if not leftovers:
        return
    folder = _parked(repo)
    manifest = {"files": [], "deleted": []}
    for rel in leftovers:
        source = wt / rel
        if source.is_file():
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            manifest["files"].append(rel)
        else:
            manifest["deleted"].append(rel)
        _git(wt, "reset", "-q", "--", rel, check=False)
        if _git(wt, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0:
            _git(wt, "checkout", "-q", "HEAD", "--", rel)
        elif source.exists():
            source.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _unpark(repo, wt):
    folder = _parked(repo)
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel in manifest["files"]:
        target = wt / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((folder / rel).read_bytes())
    for rel in manifest["deleted"]:
        with contextlib.suppress(FileNotFoundError):
            (wt / rel).unlink()
    import shutil
    shutil.rmtree(str(folder))


def regenerate(brain_root, wt):
    """Refresh index, glossary, context packs and backlinks from the committed pages; commit them if they changed.
    Runs after the rebase on the latest brain, so generated files never conflict."""
    import datetime as _dt
    from .brain import Brain, GENERATED
    from .generate import generate
    done = generate(Brain(brain_root), _dt.date.today())
    prefix = Path(brain_root).resolve().relative_to(Path(wt).resolve()).as_posix()
    specs = [f"{prefix}/{g.rstrip('/')}" for g in GENERATED] + [f"{prefix}/{d}" for d in done["deleted"]]
    specs = [spec for spec in specs if (Path(wt) / spec).exists()
             or _git(wt, "cat-file", "-e", f"HEAD:{spec}", check=False).returncode == 0]
    return bool(specs) and _commit_paths(wt, "pb(generate): refresh generated files", specs)


def save(repo, message, paths=(), confidence=(), force_review=False):
    with locked(repo):
        return _save(Path(repo), message, paths, confidence, force_review)


def _save(repo, message, paths, confidence, force_review):
    from .review import review
    brain, wt = _brain_of(repo)
    leftovers, rebasing, _ = _state(wt)
    if rebasing:
        message_ = "a conflict is being resolved in the brain copy: finish it, then run `PB save --continue`"
        raise UsageError(message_, {"error": message_, "code": "rebase-in-progress"})
    _unpark(repo, wt)
    pending = _read_pending(repo)
    restored = set()
    if pending:
        # Held pages from an earlier save that did not go out: route them again, never less strictly.
        force_review = force_review or bool(pending.get("force"))
        if _held_on_top(wt, pending):
            _git(wt, "reset", "-q", "--soft", "HEAD~1")
            _git(wt, "reset", "-q")
        restored = {f"brain/{p}" for p in pending.get("pages", [])}
        _clear_pending(repo)
    leftovers, _, _ = _state(wt)
    scope = leftovers
    if paths:
        wanted = {_as_worktree_path(wt, p) for p in paths} | restored
        scope = [f for f in leftovers if f in wanted]
    committed = False
    if scope:
        errors = _check(brain, wt, scope)
        if errors:
            return _result(errors=errors)
        in_scope = {f[len("brain/"):] for f in scope}
        routed = review(brain, "HEAD", confidence, noise_holds=False)
        guarded = {f[len("brain/"):] for f in scope if f.startswith(ALWAYS_REVIEWED)}
        held = set(in_scope) if force_review else \
            ({item["path"] for item in routed["review"]} & in_scope) | guarded
        markdown = routed.get("markdown", "")
        if force_review or guarded:
            markdown = FORCED_NOTE + markdown
        direct = sorted(in_scope - held)
        if direct:
            committed = _commit_paths(wt, message, [f"brain/{rel}" for rel in direct])
        if held:
            if _commit_paths(wt, f"{message} (review)", [f"brain/{rel}" for rel in sorted(held)]):
                _write_pending(repo, {"message": message, "pages": sorted(held), "markdown": markdown,
                                      "reviewers": routed.get("reviewers") or {"users": [], "teams": []},
                                      "force": force_review, "held": True})
                committed = True
    return _publish(repo, wt, committed)


def save_continue(repo):
    with locked(repo):
        repo = Path(repo)
        _, wt = _brain_of(repo)
        _, rebasing, _ = _state(wt)
        if not rebasing:
            raise UsageError("there is no conflict to continue: run `PB save -m MESSAGE`")
        conflicted = _conflict(wt)["files"]
        if conflicted:
            _git(wt, "add", "-A", "--", *conflicted)
        step = _git(wt, "rebase", "--continue", check=False, env={"GIT_EDITOR": "true"})
        if step.returncode:
            return _result(committed=True, conflict=_conflict(wt))
        return _publish(repo, wt, True, rebased=True)


def _conflict(wt):
    files = _git(wt, "-c", "core.quotePath=false", "diff", "--name-only", "--diff-filter=U").stdout.split("\n")
    files = [f for f in files if f]
    return {"files": files, "paths": [str(wt / f) for f in files],
            "how": "each file has <<<<<<< ======= >>>>>>> markers: merge both versions into one page "
                   "(keep every fact, drop duplicates, newer wins on contradictions), then `PB save --continue`"}


def _publish(repo, wt, committed, rebased=False):
    """Rebase on the latest brain, regenerate, push to docs/brain (retrying a lost race), send held pages to
    review. Drafts outside this save are parked meanwhile and put back at the end, unless a conflict stops it."""
    _park(repo, wt)
    out = _publish_parked(repo, wt, committed, rebased)
    if not out["conflict"]:
        _unpark(repo, wt)
    return out


def _publish_parked(repo, wt, committed, rebased):
    pending = _read_pending(repo)
    problems = []
    held = None
    for attempt in range(PUSH_ATTEMPTS):
        if not (rebased and attempt == 0):
            if not _fetch(repo):
                _, _, unpushed = _state(wt)
                return _result(saved=True, committed=committed, unpushed=unpushed,
                               problems=["offline: the pages are saved on this computer and go out with the "
                                         "next save"])
            step = _git(wt, "rebase", "-q", f"origin/{BRAIN_BRANCH}", check=False, env={"GIT_EDITOR": "true"})
            if step.returncode:
                return _result(committed=committed, conflict=_conflict(wt))
        if pending and not _held_on_top(wt, pending):
            # The rebase dropped the held commit: its content is already on docs/brain.
            _clear_pending(repo)
            pending = None
        if rebased or attempt:
            touched = _git(wt, "-c", "core.quotePath=false", "diff", "--name-only", f"origin/{BRAIN_BRANCH}",
                           "HEAD", "--", "brain").stdout.split("\n")
            errors = _check(_fresh(wt), wt, [f for f in touched if f])
            if errors:
                return _result(committed=committed, errors=errors)
        held = _head(wt) if pending else None
        if held:
            _git(wt, "reset", "-q", "--hard", "HEAD~1")
        ahead = int(_git(wt, "rev-list", "--count", f"origin/{BRAIN_BRANCH}..HEAD").stdout.strip() or 0)
        if not ahead:
            break
        generated = regenerate(wt / "brain", wt)
        if _git(wt, "push", "-q", "origin", f"HEAD:refs/heads/{BRAIN_BRANCH}", check=False).returncode == 0:
            break
        # Lost a race (or the push was refused): back to the commits of this save, then try again.
        if generated:
            _git(wt, "reset", "-q", "--hard", "HEAD~1")
        if held:
            _git(wt, "reset", "-q", "--hard", held)
            held = None
    else:
        _, _, unpushed = _state(wt)
        return _result(saved=True, committed=committed, unpushed=unpushed,
                       problems=["the brain changed many times while saving: retry the save in a moment"])
    pushed = bool(ahead)
    review_out = _send_to_review(repo, wt, pending, held) if held else None
    if review_out:
        problems += review_out.pop("problems")
    promotion = None
    if pushed:
        promotion, problem = ensure_promotion(repo)
        if problem:
            problems.append(problem)
    _, _, unpushed = _state(wt)
    return _result(saved=True, committed=committed, pushed=pushed, review=review_out, promotion=promotion,
                   unpushed=unpushed, problems=problems)


def _restore_held(repo, wt, pending, held):
    """The held pages could not be sent: put them back as unsaved changes; the next save sends them again."""
    for rel in pending["pages"]:
        path = f"brain/{rel}"
        if _git(wt, "cat-file", "-e", f"{held}:{path}", check=False).returncode == 0:
            _git(wt, "checkout", "-q", held, "--", path)
            _git(wt, "reset", "-q", "--", path)
        elif (wt / path).exists():
            (wt / path).unlink()
    _write_pending(repo, dict(pending, held=False))


def _send_to_review(repo, wt, pending, held):
    """The held commit goes to a pb/review/ branch with a PR towards docs/brain."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    head = f"{REVIEW_PREFIX}{stamp}"
    out = {"branch": head, "pages": pending["pages"], "pr": None, "problems": []}
    if _git(wt, "push", "-q", "origin", f"{held}:refs/heads/{head}", check=False).returncode:
        _restore_held(repo, wt, pending, held)
        out["branch"] = None
        out["problems"].append("the pages that need a review could not be sent: they are sent with the next save")
        return out
    owner = gh_repo(repo)
    body = pending["markdown"] + "\nSaved with pb. Merge to accept, edit the pages here to correct them, " \
                                 "close to drop them.\n"
    pr = _gh_json(["api", f"repos/{owner}/pulls", "-X", "POST", "-f", f"title={pending['message']} (review)",
                   "-f", f"head={head}", "-f", f"base={BRAIN_BRANCH}", "-f", f"body={body}"]) if owner else None
    if not pr:
        _git(wt, "push", "-q", "origin", f":refs/heads/{head}", check=False)
        _restore_held(repo, wt, pending, held)
        out["branch"] = None
        out["problems"].append("the review PR could not be opened (GitHub not reachable?): the pages that need "
                               "a review are sent with the next save")
        return out
    _clear_pending(repo)
    out["pr"] = pr.get("html_url")
    people = pending["reviewers"]
    if people.get("users") or people.get("teams"):
        args = ["api", f"repos/{owner}/pulls/{pr.get('number')}/requested_reviewers", "-X", "POST"]
        args += [x for u in people.get("users", []) for x in ("-f", f"reviewers[]={u}")]
        args += [x for t in people.get("teams", []) for x in ("-f", f"team_reviewers[]={t}")]
        if _gh_json(args) is None:
            out["problems"].append("reviewers not requested on the review PR")
    return out


def ensure_promotion(repo, owner=None):
    """The open PR from docs/brain to the default branch: found, or opened. Returns (url, problem)."""
    from .gitops import default_branch
    owner = owner or gh_repo(repo)
    if not owner:
        return None, "no GitHub repo for origin: the PR from docs/brain to the default branch was not opened"
    base = default_branch(repo)
    # gh api, not gh pr: cloud routines can only reach the REST API.
    found = _gh_json(["api", f"repos/{owner}/pulls?head={owner.split('/')[0]}:{BRAIN_BRANCH}&base={base}&state=open"])
    if found:
        return found[0].get("html_url"), None
    if found is None:
        return None, "GitHub could not be reached (gh): the PR towards the code is checked at the next save"
    pr = _gh_json(["api", f"repos/{owner}/pulls", "-X", "POST", "-f", f"title={PROMOTION_TITLE}",
                   "-f", f"head={BRAIN_BRANCH}", "-f", f"base={base}", "-f", f"body={PROMOTION_BODY}"])
    if not pr:
        return None, "the PR from docs/brain to the default branch could not be opened: it is retried at the next save"
    return pr.get("html_url"), None


def gh_repo(repo):
    """owner/name of the monorepo: github.repo in the brain's sources.md, else the origin URL."""
    from . import frontmatter
    from .gitops import _origin_repo
    sources = worktree_path(repo) / "brain/schema/sources.md"
    if sources.is_file():
        try:
            meta, _ = frontmatter.parse(sources.read_text(encoding="utf-8"))
        except Exception:
            meta = None
        github = (meta or {}).get("github")
        if isinstance(github, dict) and github.get("repo"):
            return github["repo"]
    return _origin_repo(repo)


def _gh_json(args):
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
