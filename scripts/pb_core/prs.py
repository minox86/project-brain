"""Merged pull requests that touch brain modules, read with the GitHub CLI so the LLM never sees the rest."""
import json
import subprocess

from .context import modules_for_paths
from .errors import PbError, UsageError

PAGE = 100
MAX_FILE_PAGES = 30
BODY_WORDS = 300
MATCHED_FILES_SHOWN = 20


def _gh(path):
    try:
        proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    except FileNotFoundError:
        raise PbError("gh is not installed", {"error": "the GitHub CLI (gh) is not installed", "code": "gh-missing"})
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise PbError(f"gh api {path} failed: {detail}",
                      {"error": f"gh api {path} failed: {detail}", "code": "gh-failed"})
    return json.loads(proc.stdout or "null")


def _merged_since(repo, since):
    found, page = [], 1
    while True:
        items = _gh(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={PAGE}&page={page}") or []
        found += [pr for pr in items if pr.get("merged_at") and pr["merged_at"] > since]
        if len(items) < PAGE or items[-1].get("updated_at", "") <= since:
            return sorted(found, key=lambda pr: pr["merged_at"])
        page += 1


def _files(repo, number):
    out = []
    for page in range(1, MAX_FILE_PAGES + 1):
        items = _gh(f"repos/{repo}/pulls/{number}/files?per_page={PAGE}&page={page}") or []
        out += items
        if len(items) < PAGE:
            break
    return out


def merged_prs(brain, since, repo=None):
    repo = repo or (brain.sources.get("github") or {}).get("repo")
    if not repo:
        raise UsageError("no GitHub repo: pass --repo owner/name or set github.repo in brain/.pb/schema/sources.md")
    result = {"repo": repo, "since": since, "cursor": since, "prs": [], "skipped": []}
    for pr in _merged_since(repo, since):
        result["cursor"] = max(result["cursor"], pr["merged_at"])
        changed = _files(repo, pr["number"])
        paths = [f["filename"] for f in changed] + [f["previous_filename"] for f in changed if f.get("previous_filename")]
        modules = modules_for_paths(brain, paths)
        if not modules:
            result["skipped"].append(pr["number"])
            continue
        matched = [p for p in paths if modules_for_paths(brain, [p])]
        words = (pr.get("body") or "").split()
        result["prs"].append({
            "number": pr["number"],
            "title": pr.get("title", ""),
            "url": pr.get("html_url"),
            "merged_at": pr["merged_at"],
            "modules": sorted(m.title for m in modules),
            "files": len(changed),
            "additions": sum(f.get("additions", 0) for f in changed),
            "deletions": sum(f.get("deletions", 0) for f in changed),
            "matched_files": matched[:MATCHED_FILES_SHOWN],
            "body": " ".join(words[:BODY_WORDS]),
            "body_truncated": len(words) > BODY_WORDS,
        })
    return result
