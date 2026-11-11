"""Links between pages: reading them (Markdown links and, in bodies not yet normalised, wikilinks), frontmatter
link fields (plain page titles), and normalisation, which turns a body's `[[Title]]` into Markdown links.

In a body the stored form is a Markdown link with a URL-encoded path relative to the page that holds it:
`[Association fact](../concepts/Association%20fact.md)`. Code spans, fenced and indented code blocks and HTML
comments are never read or changed."""
import posixpath
import re
import unicodedata
from collections import namedtuple
from urllib.parse import quote, unquote

from .brain import INDEX

_WIKI = (r"\[\[(?P<wtarget>[^\]|#]+)(?:#(?P<wanchor>[^\]|]*))?"
         r"(?:\|(?P<wlabel>(?:[^\[\]\n]|\[[^\[\]\n]*\])*))?\]\]")
# A target may hold spaces (`../concepts/Association fact.md`): GitHub does not follow it, normalisation encodes it.
_MD = (r"(?P<image>!?)\[(?P<label>(?:\\.|[^\]\\\n])*)\]"
       r"\((?P<href><[^>\n]*>|[^)\s]*(?: [^)\s\"]+)*)(?P<title>\s+\"[^\"\n]*\")?\)")
TOKEN = re.compile(_WIKI + "|" + _MD)
WIKILINK = re.compile(_WIKI)
CODE_SPAN = re.compile(r"(`+).+?\1")
LIST_ITEM = re.compile(r" {0,3}([-*+]|\d+[.)])[ \t]")
REFDEF = re.compile(r"( {0,3}\[[^\]\n]+\]:[ \t]*)(<[^>\n]*>|\S+)(.*)", re.S)
HEADING = re.compile(r" {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
FREE_LINK_FIELDS = ("affects", "resolves", "resolved_by")

# A link of a page: `name` the title as written (wikilink) or the target file name (Markdown link), `shown` how it
# reads in a message, `page` the page it reaches (None: broken), `how` title, alias or path.
# `anchor` is the heading id the link points to ('' for none).
Ref = namedtuple("Ref", "name shown page how anchor")


def _inline(line, comment):
    """(piece, is_code) pieces of one line, and whether an HTML comment is still open at its end."""
    out, pos = [], 0
    while pos < len(line):
        if comment:
            end = line.find("-->", pos)
            if end < 0:
                out.append((line[pos:], True))
                return out, True
            out.append((line[pos:end + 3], True))
            pos, comment = end + 3, False
            continue
        start = line.find("<!--", pos)
        chunk = line[pos:] if start < 0 else line[pos:start]
        at = 0
        for m in CODE_SPAN.finditer(chunk):
            out += [(chunk[at:m.start()], False), (m.group(0), True)]
            at = m.end()
        out.append((chunk[at:], False))
        if start < 0:
            break
        pos, comment = start, True
    return out, comment


def _segments(text):
    """(piece, is_code) pieces of text, in order: fenced and indented code blocks, inline code spans and HTML
    comments are code. A line indented by four spaces is code after a blank line, except inside a list."""
    fenced = comment = False
    blank, context = True, None  # was the previous line blank; the kind of the current block
    for line in (text or "").splitlines(keepends=True):
        if comment:
            pieces, comment = _inline(line, True)
            yield from pieces
            continue
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            yield line, True
            continue
        if fenced:
            yield line, True
            continue
        if not line.strip():
            blank = True
            yield line, False
            continue
        indented = line.startswith(("    ", "\t"))
        if indented and context != "list" and (blank or context == "code"):
            context, blank = "code", False
            yield line, True
            continue
        if LIST_ITEM.match(line):
            context = "list"
        elif not indented and (blank or context == "code"):
            context = "para"
        blank = False
        pieces, comment = _inline(line, False)
        yield from pieces


def slug(text):
    """GitHub's id for a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text).replace("`", "").replace("*", "")
    kept = "".join(c for c in text.strip().lower() if unicodedata.category(c)[0] in "LMN" or c in " -_")
    return kept.replace(" ", "-")


def heading_ids(body):
    """The ids GitHub gives the headings of a body (a repeated one gets `-1`, `-2`…)."""
    ids, seen = set(), {}
    for piece, code in _segments(body):
        m = None if code else HEADING.match(piece.rstrip("\r\n"))
        if m is None:
            continue
        base = slug(m.group(2))
        n = seen.get(base, 0)
        seen[base] = n + 1
        ids.add(base if n == 0 else f"{base}-{n}")
    return ids


def _ids(brain, page):
    cache = brain.__dict__.setdefault("_heading_ids", {})
    if page.rel not in cache:
        cache[page.rel] = heading_ids(with_heading(page.body, page.title))
    return cache[page.rel]


def _tokens(text):
    for piece, code in _segments(text):
        if not code:
            yield from TOKEN.finditer(piece)


def _wiki_parts(m):
    """(title as written, anchor, label) of a wikilink match; a `\\|` (pipe escaped in a table) separates too."""
    target = m.group("wtarget").rstrip("\\").strip()
    anchor = (m.group("wanchor") or "").rstrip("\\").strip()
    label = (m.group("wlabel") or "").strip()
    return target, anchor, label


def _local(href):
    """(path, anchor) of a relative link target, unquoted; None for URLs, anchors, absolute paths."""
    if href.startswith("<") and href.endswith(">"):
        href = href[1:-1]
    if not href or href.startswith(("#", "/")) or SCHEME.match(href):
        return None
    path, _, anchor = href.partition("#")
    return (unquote(path), anchor) if path else None


def _join(folder, path):
    return posixpath.normpath(posixpath.join(folder, path)) if folder else posixpath.normpath(path)


def is_page_path(brain, rel):
    """Could a brain-relative path be a page: a .md file in a type folder, not a README.md."""
    if not rel.endswith(".md") or rel.startswith("../") or posixpath.basename(rel) == INDEX:
        return False
    return any(rel.startswith(folder + "/") for folder in brain.type_folders())


def href(rel, folder):
    """The URL-encoded relative path from a brain-relative folder to a brain-relative file. A folder `..` is the
    repo root: the path then starts with `brain/`."""
    here = posixpath.normpath(posixpath.join("/brain", folder or "."))
    return quote(posixpath.relpath(posixpath.normpath(posixpath.join("/brain", rel)), here), safe="/")


def refs(brain, rel, body):
    """Every link of a body to a brain page (see Ref). Links to other files and URLs are left out."""
    folder = posixpath.dirname(rel)
    out = []
    for m in _tokens(body):
        if m.group("wtarget") is not None:
            name, anchor, _ = _wiki_parts(m)
            found, how = brain.lookup(name)
            out.append(Ref(name, m.group(0), found, how, slug(anchor) if anchor else ""))
            continue
        if m.group("image"):
            continue
        local = _local(m.group("href"))
        if local is None:
            continue
        target = _join(folder, local[0])
        if not is_page_path(brain, target):
            continue
        found = brain.page_at(target)
        out.append(Ref(posixpath.basename(target)[:-3], m.group(0), found, "path" if found else None,
                       unquote(local[1])))
    return out


def broken_anchor(brain, ref):
    """Does a link point to a heading its page does not have?"""
    return bool(ref.page is not None and ref.anchor and ref.anchor not in _ids(brain, ref.page))


def extract(text, brain=None, rel=""):
    """Names of the pages a text links: wikilink targets and, with a brain, the pages its Markdown links reach (the
    file name when the file is missing). Without a brain, wikilinks only."""
    if brain is None:
        return [_wiki_parts(m)[0] for m in WIKILINK.finditer(text or "")]
    return [r.page.title if r.page else r.name for r in refs(brain, rel, text)]


def _strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def is_link_field(name, typedef):
    spec = (typedef.fields if typedef else {}).get(name) or {}
    return spec.get("kind") == "link" or (spec.get("kind") == "list" and spec.get("of") == "link") \
        or name in FREE_LINK_FIELDS


def meta_links(meta, typedef):
    """[(field, title)] for link fields of the type and free link fields. Values are plain page titles; a value
    still written as a wikilink (a validation error) is read for its target."""
    out = []
    for name, value in (meta or {}).items():
        if not is_link_field(name, typedef):
            continue
        for item in _strings(value):
            targets = extract(item) if "[[" in item else [item.strip()]
            out += [(name, t) for t in targets if t]
    return out


def _label(text):
    return re.sub(r"([\[\]])", r"\\\1", text)


def rewrite(brain, body, src, dst=None, notes=None):
    """The body with its wikilinks turned into Markdown links and links to a missing page file repaired (when the
    file name is the title or an alias of a page), valid from the brain-relative folder `dst`. `src` is the folder
    the body's relative links are written from. With `dst` None (normalisation) every other link is left byte for
    byte; with a `dst` every relative link is rebased onto it (a context pack embedding page text). A wikilink
    anchor becomes the GitHub heading id; one that matches no heading of the page is dropped and noted in `notes`."""
    rebase = dst is not None and dst != src
    dst = src if dst is None else dst
    out = []
    for piece, code in _segments(body):
        if code:
            out.append(piece)
            continue
        ref = REFDEF.fullmatch(piece)
        if ref and rebase and _local(ref.group(2)) is not None:
            path, anchor = _local(ref.group(2))
            out.append(ref.group(1) + href(_join(src, path), dst) + ("#" + anchor if anchor else "") + ref.group(3))
            continue
        pos = 0
        for m in TOKEN.finditer(piece):
            out.append(piece[pos:m.start()])
            out.append(_rewrite_one(brain, m, src, dst, rebase, notes))
            pos = m.end()
        out.append(piece[pos:])
    return "".join(out)


def _rewrite_one(brain, m, src, dst, rebase, notes):
    if m.group("wtarget") is not None:
        name, anchor, label = _wiki_parts(m)
        found, _ = brain.lookup(name)
        if found is None:
            return m.group(0)
        fragment = slug(anchor) if anchor else ""
        if fragment and fragment not in _ids(brain, found):
            if notes is not None:
                notes.append(f"{m.group(0)}: '{found.title}' has no heading '{anchor}', linked to the page")
            fragment = ""
        return f"[{_label(label or name)}]({href(found.rel, dst)}{'#' + fragment if fragment else ''})"
    local = _local(m.group("href"))
    if local is None:
        return m.group(0)
    path, anchor = local
    target = _join(src, path)
    repaired = False
    if is_page_path(brain, target) and not (brain.root / target).exists():
        found, _ = brain.lookup(unquote(posixpath.basename(target)[:-3]))
        if found is not None:
            target, repaired = found.rel, True
    spaced = " " in m.group("href") and not m.group("href").startswith("<") and is_page_path(brain, target)
    if not (repaired or rebase or spaced):
        return m.group(0)
    return (f"{m.group('image')}[{m.group('label')}]({href(target, dst)}{'#' + anchor if anchor else ''}"
            f"{m.group('title') or ''})")


def _split_raw(text):
    """(frontmatter block as it is, body) of a page file."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].lstrip("﻿").rstrip("\r\n") != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            head = "".join(lines[:i + 1])
            return head if head.endswith("\n") else head + "\n", "".join(lines[i + 1:])
    return text, ""


def with_heading(body, title, eol="\n"):
    """The body starting with `# <title>`: inserted when the body does not start with a level-1 heading, and in
    place of one that names another title."""
    lines = body.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and lines[first].startswith("# "):
        if lines[first].rstrip("\r\n").rstrip() != f"# {title}":
            ending = lines[first][len(lines[first].rstrip("\r\n")):]
            lines[first] = f"# {title}" + ending
            return "".join(lines)
        return body
    if not body.strip():
        return f"# {title}{eol}"
    return f"# {title}{eol}" + ("" if body.startswith(("\n", "\r\n")) else eol) + body


def normalise_text(brain, page, text, notes=None):
    """The page file's text, normalised: Markdown links in the body and a heading. The frontmatter is untouched."""
    head, body = _split_raw(text)
    eol = "\r\n" if "\r\n" in text else "\n"
    return head + with_heading(rewrite(brain, body, posixpath.dirname(page.rel), notes=notes), page.title, eol)


def normalise(brain, rels=None, check=False, warnings=None):
    """Normalise the given brain-relative pages (default: every page). Returns the brain-relative paths changed
    (with `check`, those that would change: nothing is written). Anchors dropped go to `warnings` as findings."""
    wanted = None if rels is None else set(rels)
    changed = []
    for page in brain.pages():
        if wanted is not None and page.rel not in wanted:
            continue
        text = page.path.read_bytes().decode("utf-8")
        notes = []
        new = normalise_text(brain, page, text, notes)
        if warnings is not None:
            warnings += [{"path": page.rel, "code": "broken-anchor", "message": n} for n in notes]
        if new != text:
            if not check:
                page.path.write_bytes(new.encode("utf-8"))
            changed.append(page.rel)
    if changed and not check:
        brain.reload()
    return changed
