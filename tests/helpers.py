"""Shared test helpers."""
import contextlib
import io
import json
import os
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
    "interface": "technical/interfaces",
    "environment": "technical/environments",
    "integration": "technical/integrations",
    "role": "functional/roles",
    "decision": "decisions",
    "epic": "epics",
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
    """Create <tmp>/brain with the software-product schema plus files. Returns the repo root."""
    import shutil
    repo = Path(tmp)
    brain = repo / "brain"
    shutil.copytree(str(PRESET), str(brain / "schema"))
    for rel, text in (files or {}).items():
        target = brain / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return repo


def files_of(*pages):
    return dict(pages)
