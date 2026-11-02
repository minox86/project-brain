"""Brain model: location, schema, pages and name lookup."""
import os
from pathlib import Path

from . import frontmatter
from .errors import FrontmatterError, NotInBrain

DEFAULTS = {
    "product": None,
    "glossary_languages": ["en", "it"],
    "archive_after_days": 90,
    "open_question_stale_days": 30,
    "digest_retention_days": 30,
    "context_pack_max_words": 4000,
    "raw_max_words": 3000,
}

GENERATED = ["index.md", "glossary.md", "context/", ".pb/backlinks.json"]
MARKER = Path("schema") / "VERSION"


def find_brain(start, explicit=None):
    """The brain/ directory: explicit path, then $PB_BRAIN, then walking up from start."""
    for candidate in (explicit, os.environ.get("PB_BRAIN")):
        if candidate:
            path = Path(candidate).expanduser().resolve()
            for option in (path, path / "brain"):
                if (option / MARKER).is_file():
                    return option
            return None
    current = Path(start).resolve()
    managed = _managed_copy(current)
    if managed is not None:
        return managed
    for folder in [current] + list(current.parents):
        if (folder / MARKER).is_file() and folder.name == "brain":
            return folder
        if (folder / "brain" / MARKER).is_file():
            return folder / "brain"
    return None


def _managed_copy(start):
    """From a clone's main checkout, the brain is the managed copy on docs/brain (`PB workspace sync`), never the
    checkout's own brain/, which lags behind. Linked worktrees (the managed copy, routine runs) use their own."""
    import subprocess
    proc = subprocess.run(["git", "rev-parse", "--absolute-git-dir", "--git-common-dir"], cwd=str(start),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    lines = proc.stdout.strip().splitlines()
    if len(lines) != 2:
        return None
    git_dir, common = Path(lines[0]), Path(lines[1])
    if not common.is_absolute():
        common = (Path(start) / common).resolve()
    if git_dir.resolve() != common.resolve():
        return None
    candidate = common / "pb" / "brain-worktree" / "brain"
    return candidate if (candidate / MARKER).is_file() else None


class TypeDef:
    def __init__(self, name, meta, prose):
        self.name = name
        self.area = meta.get("area")
        self.folder = (meta.get("folder") or "").strip("/")
        self.fields = meta.get("fields") or {}
        self.required = list(meta.get("required") or [])
        self.max_words = meta.get("max_words")
        self.system = bool(meta.get("system"))
        self.prose = prose


class Page:
    def __init__(self, path, rel, meta, body):
        self.path = path
        self.rel = rel
        self.meta = meta or {}
        self.body = body
        self.title = str(self.meta.get("title") or path.stem)
        self.type = self.meta.get("type")
        self.words = len(body.split())

    def get(self, key, default=None):
        return self.meta.get(key, default)

    def __repr__(self):
        return f"Page({self.rel!r})"


class Brain:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.repo_root = self.root.parent
        self.config = dict(DEFAULTS)
        self.config.update(self._meta_of(self.root / "schema" / "brain.md"))
        self.sources = self._meta_of(self.root / "schema" / "sources.md")
        self.review = self._meta_of(self.root / "schema" / "review.md")
        self.types = self._load_types()
        self.load_errors = []
        self._pages = None
        self.by_title = {}
        self.by_alias = {}

    @classmethod
    def locate(cls, explicit=None, start=None):
        root = find_brain(Path(start or os.getcwd()), explicit)
        if root is None:
            raise NotInBrain("no brain found: run inside a repo with brain/schema/VERSION, or pass --brain")
        return cls(root)

    @staticmethod
    def _meta_of(path):
        if not path.is_file():
            return {}
        meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        return meta or {}

    def _load_types(self):
        types = {}
        folder = self.root / "schema" / "types"
        for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
            meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
            meta = meta or {}
            name = meta.get("name") or path.stem
            types[name] = TypeDef(name, meta, body)
        return types

    def type_folders(self):
        return {t.folder: t for t in self.types.values() if t.folder}

    def pages(self):
        if self._pages is None:
            self._load_pages()
        return self._pages

    def _load_pages(self):
        pages, errors, seen = [], [], set()
        for folder in sorted(self.type_folders()):
            base = self.root / folder
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.md")):
                if path in seen:
                    continue
                seen.add(path)
                rel = path.relative_to(self.root).as_posix()
                try:
                    meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
                except (FrontmatterError, UnicodeDecodeError) as exc:
                    errors.append({"path": rel, "error": str(exc)})
                    continue
                pages.append(Page(path, rel, meta, body))
        self._pages, self.load_errors = pages, errors
        self.by_title, self.by_alias = {}, {}
        for p in pages:
            self.by_title.setdefault(p.title.lower(), p)
        for p in pages:
            for alias in _as_list(p.get("aliases")):
                self.by_alias.setdefault(str(alias).lower(), p)

    def lookup(self, name):
        self.pages()
        key = name.strip().lower()
        if key in self.by_title:
            return self.by_title[key], "title"
        if key in self.by_alias:
            return self.by_alias[key], "alias"
        return None, None


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
