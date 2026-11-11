"""Brain model: location, schema, pages and name lookup."""
import os
from pathlib import Path

from . import frontmatter
from .errors import FrontmatterError, NotInBrain
from .repo import BRAIN_PR_TITLE

DEFAULTS = {
    "product": None,
    "glossary_languages": ["en", "it"],
    "archive_after_days": 90,
    "open_question_stale_days": 30,
    "digest_retention_days": 30,
    "context_pack_max_words": 4000,
    "raw_max_words": 3000,
    "commit_format": "pb({skill}): {summary}",
    "pr_title_brain": BRAIN_PR_TITLE,
    "pr_title_init": "Create the project brain",
    "commit_rules": None,
}

CONTROL = ".pb"
SCHEMA = f"{CONTROL}/schema"
CONTEXT = f"{CONTROL}/context"
DIGESTS = f"{CONTROL}/digests"
RAW = f"{CONTROL}/raw"
INDEX = "README.md"
# The index, every type folder's README.md (`*/README.md`), the context packs and the backlinks.
BACKLINKS = f"{CONTROL}/backlinks.json"
GENERATED = [INDEX, "<type folder>/" + INDEX, CONTEXT + "/", BACKLINKS]
MARKER = Path(SCHEMA) / "VERSION"
OLD_MARKER = Path("schema") / "VERSION"  # the layout before 0.6
OLD_FORMAT = "this brain has the format of an earlier pb version: remove `brain/` and create it again with /pb:init"


def is_old_format(root):
    """A brain/ in the layout of an earlier pb version: schema/VERSION at its top, no .pb/schema/VERSION."""
    root = Path(root)
    return (root / OLD_MARKER).is_file() and not (root / MARKER).is_file()


def find_old_brain(start):
    """The old-format brain/ walking up from start, or None."""
    current = Path(start).resolve()
    for folder in [current] + list(current.parents):
        for option in ([folder] if folder.name == "brain" else []) + [folder / "brain"]:
            if is_old_format(option):
                return option
    return None


def is_generated(path, folders):
    """Is a repo-relative path under brain/ a file `pb generate` writes: the index, the README.md of one of the type
    `folders`, a context pack, the backlinks?"""
    if not path.startswith("brain/"):
        return False
    rel = path[len("brain/"):]
    if rel == INDEX or rel in {f"{folder}/{INDEX}" for folder in folders}:
        return True
    return rel == BACKLINKS or rel.startswith(CONTEXT + "/")


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
    for folder in [current] + list(current.parents):
        if (folder / MARKER).is_file() and folder.name == "brain":
            return folder
        if (folder / "brain" / MARKER).is_file():
            return folder / "brain"
    return None


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
        self.words = len(_without_heading(body).split())

    def get(self, key, default=None):
        return self.meta.get(key, default)

    def __repr__(self):
        return f"Page({self.rel!r})"


class Brain:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.repo_root = self.root.parent
        self.config = dict(DEFAULTS)
        self.schema = self.root / SCHEMA
        self.config.update(self._meta_of(self.schema / "brain.md"))
        self.sources = self._meta_of(self.schema / "sources.md")
        self.review = self._meta_of(self.schema / "review.md")
        self.types = self._load_types()
        self.load_errors = []
        self._pages = None
        self.by_title = {}
        self.by_alias = {}
        self.by_rel = {}

    @classmethod
    def locate(cls, explicit=None, start=None):
        root = find_brain(Path(start or os.getcwd()), explicit)
        if root is None and find_old_brain(Path(explicit or start or os.getcwd())) is not None:
            raise NotInBrain(OLD_FORMAT, {"code": "old-format", "error": OLD_FORMAT})
        if root is None:
            raise NotInBrain(f"no brain found: run inside a repo with brain/{MARKER.as_posix()}, or pass --brain")
        return cls(root)

    @staticmethod
    def _meta_of(path):
        if not path.is_file():
            return {}
        meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        return meta or {}

    def _load_types(self):
        types = {}
        folder = self.schema / "types"
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
                if path in seen or path.name == INDEX:  # a README.md is the folder's index, never a page
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
        self.by_rel = {p.rel: p for p in pages}
        for p in pages:
            self.by_title.setdefault(p.title.lower(), p)
        for p in pages:
            for alias in _as_list(p.get("aliases")):
                self.by_alias.setdefault(str(alias).lower(), p)

    def reload(self):
        """Read the pages again (after a change on disk, e.g. normalisation)."""
        self._pages = None
        self.__dict__.pop("_heading_ids", None)

    def page_at(self, rel):
        """The page at a brain-relative path, or None."""
        self.pages()
        return self.by_rel.get(rel)

    def lookup(self, name):
        self.pages()
        key = name.strip().lower()
        if key in self.by_title:
            return self.by_title[key], "title"
        if key in self.by_alias:
            return self.by_alias[key], "alias"
        return None, None


def _without_heading(body):
    """The body without its leading `# <title>` line: the heading does not count towards the word budget."""
    stripped = body.lstrip()
    if stripped.startswith("# "):
        return stripped.split("\n", 1)[1] if "\n" in stripped else ""
    return body


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
