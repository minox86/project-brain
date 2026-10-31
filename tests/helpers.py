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
