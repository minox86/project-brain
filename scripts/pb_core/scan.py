"""Facts about a monorepo used to bootstrap the brain: modules, specs, ADRs, ownership."""
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


def scan(repo_root):
    root = Path(repo_root).resolve()
    modules, specs, adrs, readmes, ci = [], [], [], [], []
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
    }
