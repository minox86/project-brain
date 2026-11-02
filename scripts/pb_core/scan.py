"""Facts about a monorepo used to bootstrap the brain: modules, specs, ADRs, ownership, documentation."""
import fnmatch
import os
from pathlib import Path

SKIP = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "brain", "target", "__pycache__", ".next"}
MANIFESTS = ["package.json", "pyproject.toml", "setup.py", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
             "Cargo.toml", "composer.json", "*.csproj"]
SPECS = [("openapi*.yaml", "openapi"), ("openapi*.yml", "openapi"), ("openapi*.json", "openapi"),
         ("swagger*.yaml", "openapi"), ("swagger*.yml", "openapi"), ("swagger*.json", "openapi"),
         ("asyncapi*.yaml", "asyncapi"), ("asyncapi*.yml", "asyncapi"), ("asyncapi*.json", "asyncapi"),
         ("*.proto", "proto"), ("*.graphql", "graphql")]
ADR_DIRS = {"adr", "adrs", "decisions"}
CODEOWNERS = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]
CI_FILES = [".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", "bitbucket-pipelines.yml"]
MAX_MODULE_DEPTH = 3
DOC_EXTENSIONS = (".md", ".mdx", ".rst", ".adoc", ".asciidoc")
DOC_DIRS = {"docs", "doc", "documentation", "wiki", "handbook", "guides", "rfcs", "rfc", "design"}
# Not product knowledge: history, legal, agent instructions, test data.
NOT_DOCS = ("changelog", "changes", "license", "licence", "copying", "notice", "code_of_conduct", "security",
            "claude", "agents", "pull_request_template", "issue_template")
NOT_DOC_DIRS = {"test", "tests", "__tests__", "fixtures", "testdata", "__fixtures__", "__snapshots__"}


def _doc_facts(path):
    """Title (frontmatter `title`, first heading, else first line of text) and word count of a documentation file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, 0
    lines = text.splitlines()
    front_title = None
    if lines and lines[0].strip() == "---":
        end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
        if end is not None:
            for line in lines[1:end]:
                if line.startswith("title:"):
                    front_title = line[6:].strip().strip("\"'") or None
            lines = lines[end + 1:]
    heading = first = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith(("<", "[!", "```")) or set(line) <= set("=-~*#^"):
            continue
        if line.startswith(("#", "= ")):
            heading = line.lstrip("#=").strip()
            break
        if i + 1 < len(lines) and lines[i + 1].strip() and set(lines[i + 1].strip()) <= set("=-~^"):
            heading = line  # reStructuredText / setext title
            break
        first = first or line
    title = front_title or heading or first
    return (title[:120] if title else None), len(text.split())


def scan(repo_root):
    root = Path(repo_root).resolve()
    modules, specs, adrs, readmes, ci, docs = [], [], [], [], [], []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        rel_dir = Path(folder).relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        depth = len(rel_dir.split("/")) if rel_dir else 0

        def rel(name):
            return f"{rel_dir}/{name}" if rel_dir else name

        if 0 < depth <= MAX_MODULE_DEPTH:
            for pattern in MANIFESTS:
                match = sorted(f for f in files if fnmatch.fnmatch(f, pattern))
                if match:
                    modules.append({"name": Path(rel_dir).name, "path": rel_dir, "manifest": match[0]})
                    break
        for name in files:
            for pattern, kind in SPECS:
                if fnmatch.fnmatch(name.lower(), pattern):
                    specs.append({"path": rel(name), "kind": kind})
                    break
            if name.lower().endswith(".md") and ADR_DIRS & set(rel_dir.lower().split("/")):
                adrs.append(rel(name))
            if name.lower().startswith("readme"):
                readmes.append(rel(name))
        parts = set(rel_dir.lower().split("/")) if rel_dir else set()
        hidden = any(p.startswith(".") for p in parts)
        is_adr_dir = bool(ADR_DIRS & parts)
        if not hidden and not is_adr_dir and not NOT_DOC_DIRS & parts:
            for name in files:
                lower = name.lower()
                if not lower.endswith(DOC_EXTENSIONS) or lower.split(".")[0] in NOT_DOCS:
                    continue
                if lower.startswith("readme"):
                    kind = "readme"
                elif DOC_DIRS & parts:
                    kind = "docs"
                elif not rel_dir:
                    kind = "root"
                else:
                    kind = "other"
                title, words = _doc_facts(Path(folder) / name)
                docs.append({"path": rel(name), "kind": kind, "title": title, "words": words})
        if rel_dir == ".github/workflows":
            ci.extend(rel(f) for f in files if f.endswith((".yml", ".yaml")))
    ci.extend(f for f in CI_FILES if (root / f).is_file())
    top = sorted(d.name for d in root.iterdir() if d.is_dir() and d.name not in SKIP and not d.name.startswith("."))
    owners = next((c for c in CODEOWNERS if (root / c).is_file()), None)
    return {
        "modules": sorted(modules, key=lambda m: m["path"]),
        "specs": sorted(specs, key=lambda s: s["path"]),
        "adrs": sorted(adrs),
        "codeowners": owners,
        "readmes": sorted(readmes),
        "ci": sorted(ci),
        "top_level": top,
        "docs": sorted(docs, key=lambda d: d["path"]),
        "docs_words": sum(d["words"] for d in docs),
    }
