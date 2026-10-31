"""Command line interface: argument parsing, dispatch, JSON output, exit codes."""
import argparse
import datetime
import json
import subprocess
import sys
import traceback
from pathlib import Path

from . import FORMAT_VERSION, __version__
from .brain import Brain, find_brain
from .context import build_context
from .generate import generate
from .lint import lint
from .stats import stats
from . import gitops, state
from .scaffold import scaffold, sync_toolkit
from .scan import scan
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


def _cmd_state(args):
    brain = _brain(args)
    if args.action == "get":
        return {"source": args.source, "key": args.key, "value": state.get(brain, args.source, args.key)}, 0
    if args.action == "set":
        if args.key is None or args.value is None:
            raise UsageError("usage: pb state set <source> <key> <json-value>")
        try:
            value = json.loads(args.value)
        except ValueError:
            raise UsageError("value must be valid JSON (quote strings: '\"text\"')")
        state.set_(brain, args.source, args.key, value)
        return {"source": args.source, "key": args.key, "value": value}, 0
    if args.key is None:
        raise UsageError("usage: pb state suppress <source> \"<claim>\"")
    return {"source": args.source, "suppressed": state.suppress(brain, args.source, args.key)}, 0


def _cmd_correction(args):
    return state.add_correction(_brain(args), args.page, args.wrong, args.right, args.evidence, _today(args)), 0


def _cmd_commit(args):
    return gitops.commit(_brain(args), args.message, args.allow_default, args.include or ()), 0


def _cmd_routine(args):
    brain = _brain(args)
    if args.action == "discard":
        return gitops.routine_discard(brain), 0
    if args.action == "cleanup":
        if not args.worktree:
            raise UsageError("pb routine cleanup needs --worktree")
        return gitops.routine_cleanup(brain, args.worktree), 0
    if not args.branch:
        raise UsageError(f"pb routine {args.action} needs --branch")
    if args.action == "start":
        return gitops.routine_start(brain, args.branch, args.worktree), 0
    if not args.message:
        raise UsageError("pb routine finish needs -m MESSAGE")
    result = gitops.routine_finish(brain, args.branch, args.message)
    return result, 1 if result["conflict"] else 0


def _repo_arg(args):
    if args.repo:
        return Path(args.repo)
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(proc.stdout.strip()) if proc.returncode == 0 else Path.cwd()


def _cmd_scan(args):
    return scan(_repo_arg(args)), 0


def _cmd_scaffold(args):
    return scaffold(_repo_arg(args), args.product, args.preset), 0


def _cmd_toolkit_sync(args):
    brain = _brain(args)
    return {"toolkit": str(sync_toolkit(brain.root)), "version": __version__}, 0


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
    p = sub.add_parser("state")
    p.add_argument("action", choices=["get", "set", "suppress"])
    p.add_argument("source")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(handler=_cmd_state)
    p = sub.add_parser("correction")
    for name in ("--page", "--wrong", "--right", "--evidence"):
        p.add_argument(name, required=True)
    p.add_argument("--today")
    p.set_defaults(handler=_cmd_correction)
    p = sub.add_parser("commit")
    p.add_argument("-m", "--message", required=True)
    p.add_argument("--allow-default", action="store_true")
    p.add_argument("--include", nargs="+", help="extra repo paths to commit (e.g. CI workflows from init)")
    p.set_defaults(handler=_cmd_commit)
    p = sub.add_parser("routine")
    p.add_argument("action", choices=["start", "finish", "discard", "cleanup"])
    p.add_argument("--branch")
    p.add_argument("--worktree", help="manual runs: work in a detached worktree at this path")
    p.add_argument("-m", "--message")
    p.set_defaults(handler=_cmd_routine)
    p = sub.add_parser("scan")
    p.add_argument("--repo")
    p.set_defaults(handler=_cmd_scan)
    p = sub.add_parser("scaffold")
    p.add_argument("--repo")
    p.add_argument("--product", required=True)
    p.add_argument("--preset", default="software-product")
    p.set_defaults(handler=_cmd_scaffold)
    sub.add_parser("toolkit-sync").set_defaults(handler=_cmd_toolkit_sync)
    p = sub.add_parser("lint")
    p.add_argument("--today")
    p.set_defaults(handler=_cmd_lint)
    p = sub.add_parser("validate")
    p.add_argument("paths", nargs="*")
    p.set_defaults(handler=_cmd_validate)
    return parser
