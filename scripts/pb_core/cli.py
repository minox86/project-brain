"""Command line interface: argument parsing, dispatch, JSON output, exit codes."""
import argparse
import datetime
import json
import sys
import traceback
from pathlib import Path

from . import FORMAT_VERSION, __version__
from .brain import Brain, find_brain
from .context import build_context
from .generate import generate
from .lint import lint
from .stats import stats
from .errors import PbError, UsageError
from .resolve import resolve
from .validate import validate


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"pb: {message}", file=sys.stderr)
        _emit({"error": message})
        raise SystemExit(2)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.error("missing command")
    try:
        result, code = args.handler(args)
    except PbError as exc:
        print(f"pb: {exc}", file=sys.stderr)
        _emit(exc.payload or {"error": str(exc)})
        return 2
    except Exception as exc:  # unexpected: still honour the JSON + exit 2 contract
        traceback.print_exc(file=sys.stderr)
        _emit({"error": f"internal error: {type(exc).__name__}: {exc}"})
        return 2
    _emit(result)
    return code


def _emit(data):
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _brain(args):
    return Brain.locate(getattr(args, "brain", None))


def _cmd_version(args):
    root = find_brain(Path.cwd(), args.brain)
    return {"version": __version__, "format": FORMAT_VERSION, "brain": str(root) if root else None}, 0


def _cmd_resolve(args):
    return {"candidates": resolve(_brain(args), args.name, args.type)}, 0


def _cmd_validate(args):
    result = validate(_brain(args), args.paths or None)
    return result, 1 if result["errors"] else 0


def _cmd_context(args):
    return build_context(_brain(args), jira=args.jira, feature=args.feature,
                         paths=args.paths, max_words=args.max_words), 0


def _today(args):
    value = getattr(args, "today", None)
    if not value:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise UsageError("--today must be YYYY-MM-DD")


def _cmd_generate(args):
    return generate(_brain(args), _today(args)), 0


def _cmd_lint(args):
    result = lint(_brain(args), _today(args))
    return result, 1 if result["findings"] else 0


def _cmd_stats(args):
    return stats(_brain(args)), 0


def build_parser():
    parser = _Parser(prog="pb", description="project-brain toolkit")
    parser.add_argument("--brain", help="path of the brain/ directory")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)
    sub.add_parser("version").set_defaults(handler=_cmd_version)
    p = sub.add_parser("resolve")
    p.add_argument("name")
    p.add_argument("--type")
    p.set_defaults(handler=_cmd_resolve)
    p = sub.add_parser("context")
    seed = p.add_mutually_exclusive_group(required=True)
    seed.add_argument("--jira")
    seed.add_argument("--feature")
    seed.add_argument("--paths", nargs="+")
    p.add_argument("--max-words", type=int)
    p.set_defaults(handler=_cmd_context)
    p = sub.add_parser("generate")
    p.add_argument("--today")
    p.set_defaults(handler=_cmd_generate)
    sub.add_parser("stats").set_defaults(handler=_cmd_stats)
    p = sub.add_parser("lint")
    p.add_argument("--today")
    p.set_defaults(handler=_cmd_lint)
    p = sub.add_parser("validate")
    p.add_argument("paths", nargs="*")
    p.set_defaults(handler=_cmd_validate)
    return parser
