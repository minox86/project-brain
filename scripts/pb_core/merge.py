"""/pb:merge: bring the default branch into docs/brain in a temporary worktree, then land the Brain updates PR.

Only docs/brain is ever pushed; the default branch is reached only by merging the PR through the GitHub API.
"""
import json
import time
from pathlib import Path

from . import frontmatter, links
from .brain import MARKER, SCHEMA as SCHEMA_DIR, Brain
from .errors import FrontmatterError, GitError, UsageError
from .generate import generate
from .gitops import adds_nothing, routine_cleanup, try_commit
from .messages import compose, pr_title
from .repo import BRAIN_BRANCH, BRAIN_PR_TITLE, default_branch, ensure_brain_pr, gh_json, gh_repo, git, origin_repo
from .save import _generated, check
from .state import _save

STATE = "brain/.pb/state/"
SCHEMA = (f"brain/{SCHEMA_DIR}/", "brain/.pb/toolkit/")
OK_CHECKS = ("success", "neutral", "skipped")
MERGEABLE = ("clean", "unstable", "has_hooks")


def _names(cwd, *args, paths=()):
    out = git(cwd, "-c", "core.quotePath=false", *args, "-z", "--", *paths).stdout
    return sorted({f for f in out.split("\0") if f})


def _unmerged(cwd):
    return _names(cwd, "diff", "--name-only", "--diff-filter=U")


def _count(cwd, spec):
    return int(git(cwd, "rev-list", "--count", spec).stdout.strip())


PB_OWN = ("brain/.pb/toolkit/", "brain/.pb/state/", "brain/.pb/corrections.md")


def _type_folders(cwd, *refs):
    """The type folders of the brain schema at each ref, together (a type one side added counts too)."""
    folders = set()
    for ref in refs:
        listed = git(cwd, "ls-tree", "-z", "--name-only", ref, "--", "brain/.pb/schema/types/", check=False)
        for path in (p for p in listed.stdout.split("\0") if p.endswith(".md")):
            shown = git(cwd, "show", f"{ref}:{path}", check=False)
            try:
                meta, _ = frontmatter.parse(shown.stdout) if shown.returncode == 0 else (None, "")
            except FrontmatterError:
                meta = None
            if meta and meta.get("folder"):
                folders.add(str(meta["folder"]).strip("/"))
    return folders


def _pages(names, folders):
    """Brain files a person writes (pages, the schema, digests, raw text): not generated, not pb's own files."""
    return [f for f in names if f.startswith("brain/") and not _generated(f, folders) and not f.startswith(PB_OWN)]


def _take_ours(cwd, path):
    """Resolve a conflicted path with the docs/brain side (deleted there: deleted)."""
    if git(cwd, "checkout", "--ours", "--", path, check=False).returncode == 0:
        git(cwd, "add", "--", path)
    else:
        git(cwd, "rm", "-q", "--cached", "--ignore-unmatch", "--", path)
        (Path(cwd) / path).unlink(missing_ok=True)


def _stage(cwd, path, n):
    """The JSON of a conflicted path at merge stage n (2: docs/brain, 3: the default branch); None if absent or invalid."""
    shown = git(cwd, "show", f":{n}:{path}", check=False)
    if shown.returncode:
        return None
    try:
        data = json.loads(shown.stdout)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _merge_state(cwd, path):
    """A conflicted state file keeps docs/brain's cursors and the union of both sides' suppressions. Either side
    missing or not valid JSON: the docs/brain side, as it is."""
    ours, theirs = _stage(cwd, path, 2), _stage(cwd, path, 3)
    if ours is None or theirs is None:
        return _take_ours(cwd, path)
    mine, other = ours.get("suppressed") or [], theirs.get("suppressed") or []
    if not isinstance(mine, list) or not isinstance(other, list):
        return _take_ours(cwd, path)
    union = list(mine)
    for claim in other:
        if claim not in union:
            union.append(claim)
    if len(union) == len(mine):  # nothing new from the default branch: docs/brain's file as it is
        return _take_ours(cwd, path)
    _save(Path(cwd) / path, dict(ours, suppressed=union))
    git(cwd, "add", "--", path)


def merge_start(repo, worktree):
    repo = Path(repo)
    git(repo, "fetch", "-q", "--prune", "origin")
    base_branch = default_branch(repo)
    if git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{BRAIN_BRANCH}", check=False).returncode:
        raise UsageError(f"no {BRAIN_BRANCH} on origin: the routine has written nothing to merge")
    theirs, ours = f"origin/{base_branch}", f"origin/{BRAIN_BRANCH}"
    base = git(repo, "merge-base", theirs, ours).stdout.strip()
    folders = _type_folders(repo, ours, theirs)
    out = {"alert": None, "files": [], "worktree": None, "brain": None, "base": base,
           "behind": _count(repo, f"{ours}..{theirs}"), "ahead": _count(repo, f"{theirs}..{ours}"),
           "conflicts": {"pages": [], "schema": [], "generated": [], "state": []},
           "changed": {"routine": _pages(_names(repo, "diff", "--name-only", base, ours, paths=["brain"]), folders),
                       "default": _pages(_names(repo, "diff", "--name-only", base, theirs, paths=["brain"]),
                                         folders)}}
    if adds_nothing(repo, BRAIN_BRANCH, base_branch):  # e.g. the Brain updates PR was squash-merged
        return dict(out, alert="nothing-to-merge")
    outside = [f for f in _names(repo, "diff", "--name-only", f"{theirs}...{ours}") if not f.startswith("brain/")]
    if outside:
        return dict(out, alert="outside-brain", files=outside)
    git(repo, "worktree", "add", "-q", "--detach", str(worktree), ours)
    worktree = Path(worktree).resolve()
    out.update(worktree=str(worktree), brain=str(worktree / "brain"))
    merged = git(worktree, "merge", "-q", "--no-commit", "--no-ff", theirs, check=False)
    unmerged = _unmerged(worktree)
    if merged.returncode and not unmerged:
        routine_cleanup(repo, worktree)
        raise GitError(f"git merge {theirs} failed: {merged.stderr.strip() or merged.stdout.strip()}")
    outside = [f for f in unmerged if not f.startswith("brain/")]
    if outside:  # a rename can carry a conflict out of brain/
        git(worktree, "merge", "--abort", check=False)
        routine_cleanup(repo, worktree)
        return dict(out, alert="outside-brain", files=outside, worktree=None, brain=None)
    conflicts = out["conflicts"]
    for f in unmerged:
        if _generated(f, folders):
            conflicts["generated"].append(f)
        elif f.startswith(STATE):
            _merge_state(worktree, f)  # docs/brain's cursors, both sides' suppressions
            conflicts["state"].append(f)
        elif f.startswith(SCHEMA):
            conflicts["schema"].append(f)
        else:
            conflicts["pages"].append(f)
    return out


def _on_top_of_brain_branch(worktree):
    """The worktree of `merge start`: detached, origin/docs/brain at HEAD (merge in progress) or below it (concluded)."""
    detached = git(worktree, "symbolic-ref", "-q", "HEAD", check=False).returncode != 0
    on_top = git(worktree, "merge-base", "--is-ancestor", f"origin/{BRAIN_BRANCH}", "HEAD", check=False).returncode == 0
    if not (detached and on_top):
        raise UsageError(f"{worktree} is not the worktree of `pb merge start` (detached, on top of origin/{BRAIN_BRANCH}): "
                         "nothing was changed")


def merge_finish(repo, worktree, summary, raw=False):
    """Settle the generated files, regenerate, run the save checks, commit the merge and push docs/brain. A commit
    the repo's hooks reject leaves the merge in progress, for a retry with a message given in full (`raw`)."""
    worktree = Path(worktree).resolve()
    _on_top_of_brain_branch(worktree)
    out = {"committed": False, "pushed": False, "errors": [], "unresolved": [], "problems": [], "rejected": None}
    unmerged = _unmerged(worktree)
    theirs = f"origin/{default_branch(repo)}"
    folders = _type_folders(worktree, "HEAD", theirs)
    out["unresolved"] = [f for f in unmerged if not _generated(f, folders)]
    if out["unresolved"]:
        return out
    for f in unmerged:  # either side: generate rewrites them
        _take_ours(worktree, f)
    git(worktree, "add", "-A", "--", "brain")
    fork = git(worktree, "merge-base", "HEAD", theirs).stdout.strip()
    files = set(_names(worktree, "diff", "--cached", "--name-only", "HEAD", paths=["brain"]))
    for side in ("HEAD", theirs):
        files.update(_names(worktree, "diff", "--name-only", fork, side, paths=["brain"]))
    pages = sorted(f for f in files if not _generated(f, folders))
    brain = Brain(worktree / "brain")
    # The pages either side brought: their links and headings normalised before the checks; every page when a
    # page file was deleted, renamed or moved, so the links to it are repaired.
    gone = any(not (worktree / f).exists() for f in pages if links.is_page_path(brain, f[len("brain/"):]))
    links.normalise(brain, None if gone else [f[len("brain/"):] for f in pages if f.startswith("brain/")])
    generate(brain)
    git(worktree, "add", "-A", "--", "brain")
    out["errors"] = check(Brain(worktree / "brain"), worktree, pages)
    if out["errors"]:
        return out
    merging = git(worktree, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0
    if merging or git(worktree, "diff", "--cached", "--quiet", check=False).returncode:
        out["rejected"] = try_commit(worktree, compose(Brain(worktree / "brain"), "merge", summary, raw))
        if out["rejected"]:
            out["problems"].append("the commit was rejected by the repo's commit rules")
            return out
        out["committed"] = True
    if git(worktree, "push", "-q", "origin", f"HEAD:refs/heads/{BRAIN_BRANCH}", check=False).returncode:
        out["problems"].append(f"the push to {BRAIN_BRANCH} was refused ({BRAIN_BRANCH} moved on origin, probably a "
                               "routine run): clean up and run /pb:merge again")
    else:
        out["pushed"] = True
    return out


def _pr_title(repo):
    root = Path(repo) / "brain"
    return pr_title(Brain(root), "brain") if (root / MARKER).is_file() else BRAIN_PR_TITLE


def _owner(repo):
    root = Path(repo) / "brain"
    return gh_repo(Brain(root)) if (root / MARKER).is_file() else origin_repo(repo)


def merge_land(repo, wait=600, interval=15, sleep=time.sleep):
    """Wait for the checks of the Brain updates PR and merge it through the GitHub API. Never pushes."""
    repo = Path(repo)
    out = {"merged": False, "pr": None, "missing": [], "problems": []}
    git(repo, "fetch", "-q", "--prune", "origin")
    base = default_branch(repo)
    owner = _owner(repo)
    if not owner:
        out["problems"].append("no GitHub repo (github.repo in sources.md): the brain PR cannot be merged")
        return out
    if adds_nothing(repo, BRAIN_BRANCH, base):
        out["problems"].append(f"{BRAIN_BRANCH} holds nothing {base} lacks: there is nothing to merge")
        return out
    found = gh_json(["api", f"repos/{owner}/pulls?head={owner.split('/')[0]}:{BRAIN_BRANCH}&base={base}&state=open"])
    if found is None:
        out["problems"].append("GitHub could not be reached (gh): the brain PR was not checked")
        return out
    if found:  # found, not refreshed: its description is the routine's
        out["pr"], number = found[0].get("html_url"), found[0].get("number")
    else:
        body = (f"Brain pages the pb routine wrote on `{BRAIN_BRANCH}`, brought up to date with `{base}` by "
                f"`/pb:merge`. Merging this PR brings them to `{base}`.\n")
        out["pr"], number, problem, _ = ensure_brain_pr(owner, base, body, _pr_title(repo))
        if problem:
            out["problems"].append(problem)
        if number is None:
            return out
    waited, seen_none = 0, False
    while True:
        pr = gh_json(["api", f"repos/{owner}/pulls/{number}"])
        sha = ((pr or {}).get("head") or {}).get("sha")
        runs = gh_json(["api", f"repos/{owner}/commits/{sha}/check-runs"]) if sha else None
        if runs is None:
            out["problems"].append("GitHub could not be reached (gh): the checks of the brain PR were "
                                   "not read")
            return out
        runs = (runs.get("check_runs") or []) if isinstance(runs, dict) else []
        failed = [r.get("name") for r in runs if r.get("status") == "completed"
                  and r.get("conclusion") not in OK_CHECKS]
        if failed:
            out["missing"] = [f"check {name} failed" for name in failed]
            return out
        pending = [r.get("name") for r in runs if r.get("status") != "completed"]
        # No check run yet: the checks may not have started. Wait one interval before taking it as none.
        too_early = not runs and not seen_none
        seen_none = seen_none or not runs
        state = pr.get("mergeable_state")
        if not pending and not too_early and state not in (None, "unknown"):
            break
        if waited >= wait:
            out["missing"] = [f"checks still running: {', '.join(pending)} (run /pb:merge again once they finish)"
                              if pending else "no check has reported on the PR yet: run /pb:merge again"
                              if too_early else "GitHub has not yet worked out whether the PR can be merged: "
                                                "run /pb:merge again"]
            return out
        sleep(interval)
        waited += interval
    if state not in MERGEABLE:
        out["missing"] = [_why_not(state, base, pr)]
        return out

    def put(method):
        return gh_json(["api", f"repos/{owner}/pulls/{number}/merge", "-X", "PUT",
                        "-f", f"merge_method={method}", "-f", f"sha={sha}"])
    done = put("merge")
    if done is None and (gh_json(["api", f"repos/{owner}"]) or {}).get("allow_merge_commit") is False:
        done = put("squash")  # merge commits are disabled on this repository
    out["merged"] = bool(isinstance(done, dict) and done.get("merged"))
    if not out["merged"]:
        out["problems"].append(f"GitHub refused to merge the brain PR: see {out['pr']}")
    return out


def _why_not(state, base, pr):
    if state == "blocked":
        who = [u.get("login") for u in pr.get("requested_reviewers") or [] if u.get("login")]
        who += [f"team {t.get('slug')}" for t in pr.get("requested_teams") or [] if t.get("slug")]
        return (f"an approval or another rule of {base} (see the PR)"
                + (f": review requested from {', '.join(who)}" if who else ""))
    if state == "dirty":
        return f"the PR conflicts with {base}: run /pb:merge again to bring {base} into {BRAIN_BRANCH}"
    if state == "behind":
        return f"{base} moved on since {BRAIN_BRANCH} was brought up to date: run /pb:merge again"
    if state == "draft":
        return "the PR is a draft: mark it ready for review"
    return f"GitHub reports the PR as '{state}': see the PR"
