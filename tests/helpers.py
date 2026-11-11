"""Shared test helpers."""
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pb_core.cli import main  # noqa: E402


def run_cli(*argv, cwd=None):
    """Run the CLI in-process. Returns (exit_code, json_stdout | None, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    if cwd is not None:
        os.chdir(str(cwd))
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main([str(a) for a in argv])
            except SystemExit as exc:  # argparse usage errors or --help
                code = exc.code
    finally:
        os.chdir(old)
    text = out.getvalue().strip()
    data = json.loads(text) if text.startswith("{") else None
    return code, data, err.getvalue()


PRESET = ROOT / "presets" / "software-product"

FOLDERS = {
    "feature": "functional/features",
    "concept": "functional/concepts",
    "module": "technical/modules",
    "contract": "technical/contracts",
    "environment": "technical/environments",
    "integration": "technical/integrations",
    "role": "functional/roles",
    "process": "functional/processes",
    "decision": "decisions",
    "open-question": "open-questions",
}


def page(type_, title, meta="", body="Body.\n"):
    """(relative path, text) of a brain page of the given type."""
    lines = [f"type: {type_}", f'title: "{title}"']
    if meta.strip():
        lines.append(meta.strip("\n"))
    text = "---\n" + "\n".join(lines) + "\n---\n" + body
    return f"{FOLDERS[type_]}/{title}.md", text


def make_brain(tmp, files=None):
    """Create <tmp>/brain with the software-product schema (in brain/.pb/schema) plus files. Returns the repo root."""
    import shutil
    repo = Path(tmp)
    brain = repo / "brain"
    shutil.copytree(str(PRESET), str(brain / ".pb" / "schema"))
    for rel, text in (files or {}).items():
        target = brain / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return repo


def files_of(*pages):
    return dict(pages)


MD_LINK = re.compile(r"!?\[(?:\\.|[^\]\\\n])*\]\((<[^>\n]*>|[^)\s]*)(?:\s+\"[^\"\n]*\")?\)")


def relative_links(path):
    """The relative link targets of a Markdown file, outside fenced code blocks and code spans."""
    out, fenced = [], False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        for m in MD_LINK.finditer(re.sub(r"(`+).+?\1", "", line)):
            target = m.group(1).strip("<>")
            if target and not target.startswith(("#", "/")) and not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                out.append(target)
    return out


def assert_links_resolve(case, paths):
    """Every relative link of every file in `paths` points to an existing file, and its `#anchor` to a heading id
    of that file (as GitHub makes them). Returns how many links were read."""
    from urllib.parse import unquote
    from pb_core import frontmatter
    from pb_core.links import heading_ids
    count = 0
    for path in paths:
        for target in relative_links(path):
            count += 1
            file, _, anchor = target.partition("#")
            resolved = (Path(path).parent / unquote(file)).resolve() if file else Path(path)
            case.assertTrue(resolved.exists(), f"{path}: {target} does not resolve")
            if anchor and resolved.suffix == ".md":
                _, body = frontmatter.split(resolved.read_text(encoding="utf-8"))
                case.assertIn(unquote(anchor), heading_ids(body), f"{path}: {target}: no such heading")
    return count
