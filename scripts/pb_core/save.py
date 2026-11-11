"""Saving pages in the working tree: check them, regenerate the generated files, report the watched points.

The pages are ordinary files of the developer's branch: a save never commits, pushes, rebases or switches branch.
"""
from pathlib import Path

from . import frontmatter
from .brain import GENERATED, MARKER, Brain
from .errors import UsageError
from .generate import generate
from .repo import default_branch, git
from .review import review
from .secrets import scan
from .validate import validate

ALWAYS_REVIEWED = ("brain/schema/", "brain/.pb/toolkit/")
ALWAYS_REVIEWED_REASON = "configuration or toolkit change: always reviewed"
NO_BRAIN = "no brain/ in this checkout: bring the default branch into your branch, or create the brain with /pb:init"


def save(repo, paths=()):
    repo = Path(repo)
    root = repo / "brain"
    if not (root / MARKER).is_file():
        raise UsageError(NO_BRAIN, {"code": "no-brain", "error": NO_BRAIN})
    brain = Brain(root)
    changed = [f for f in _status(repo) if not _generated(f)]
    if paths:
        wanted = sorted({_as_repo_path(repo, p) for p in paths})
        unknown = [w for w in wanted if w not in changed and not (repo / w).exists()
                   and git(repo, "cat-file", "-e", f"HEAD:{w}", check=False).returncode]
        scope = [w for w in wanted if not _generated(w) and w not in unknown]
        errors = [{"path": w, "code": "not-in-brain", "message": f"{w} is neither in the brain at {root} nor in "
                                                                 "HEAD: write pages under brain/"} for w in unknown]
    else:
        scope, errors = changed, []
    errors += check(brain, repo, scope)
    out = {"saved": False, "errors": errors, "files": [], "watched": [], "reviewers": {"users": [], "teams": []},
           "markdown": "", "branch": git(repo, "branch", "--show-current").stdout.strip()}
    out["on_default"] = out["branch"] == default_branch(repo)
    if not errors:
        generate(brain)
        routed = review(brain, "HEAD", noise_holds=False)
        out["watched"] = [{"path": item["path"], "reason": "; ".join(item["reasons"])} for item in routed["review"]]
        out["watched"] += [{"path": f[len("brain/"):], "reason": ALWAYS_REVIEWED_REASON}
                           for f in scope if f.startswith(ALWAYS_REVIEWED)]
        reviewers = routed.get("reviewers") or {}
        out["reviewers"] = {"users": reviewers.get("users") or [], "teams": reviewers.get("teams") or []}
        out["markdown"] = routed.get("markdown", "")
        out["saved"] = True
    out["files"] = _status(repo)
    return out


def check(brain, repo, files):
    """Errors in what this save touches: a secret in any touched file, invalid touched pages (against HEAD),
    links left pointing at a page the save deletes. `files` are repo-relative. Problems of other pages never
    block it."""
    repo = Path(repo)
    errors = []
    for f in files:
        path = repo / f
        if path.is_file():
            text = path.read_bytes().decode("utf-8", errors="replace")
            for hit in scan(text):
                errors.append({"path": f, "code": "secret", "message": f"line {hit['line']} looks like a "
                               f"{hit['kind']}: remove it (never work around the check)"})
    pages = [str(repo / f) for f in files if f.startswith("brain/") and f.endswith(".md") and (repo / f).is_file()]
    if pages:
        errors += [e for e in validate(brain, pages, "HEAD")["errors"] if e["code"] != "secret"]
    gone = []
    for f in files:
        if f.endswith(".md") and not (repo / f).exists():
            old = git(repo, "show", f"HEAD:{f}", check=False)
            if old.returncode == 0:
                try:
                    meta, _ = frontmatter.parse(old.stdout)
                except Exception:
                    meta = None
                if meta and meta.get("title"):
                    gone.append(str(meta["title"]))
    if gone:
        for e in validate(brain)["errors"]:
            if e["code"] == "broken-link" and any(f"[[{t}]]" in e["message"] for t in gone):
                errors.append(dict(e, message=e["message"] + " (the page was deleted by this save: fix the link "
                                                             "or keep the page)"))
    return errors


def _status(repo):
    """Repo-relative paths under brain/ that differ from HEAD or are untracked (both sides of a rename)."""
    out = git(repo, "-c", "core.quotePath=false", "status", "--porcelain", "-z", "--untracked-files=all", "--",
              "brain").stdout
    fields, files = out.split("\0"), []
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        files.append(entry[3:])
        if entry[0] in "RC" and i < len(fields):
            files.append(fields[i])
            i += 1
    return sorted(set(files))


def _generated(path):
    rel = path[len("brain/"):] if path.startswith("brain/") else path
    return any(rel == g or (g.endswith("/") and rel.startswith(g)) for g in GENERATED)


def _as_repo_path(repo, raw):
    path = Path(raw)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return path.as_posix()
    rel = path.as_posix()
    return rel if rel.startswith("brain/") else f"brain/{rel}"
