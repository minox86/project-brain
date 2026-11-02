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
from . import gitops, state, workspace
from .scaffold import scaffold, sync_toolkit, upgrade
from .scan import scan
from .errors import PbError, UsageError
from .prs import merged_prs
from .resolve import resolve
from .review import review
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


def _cmd_prs(args):
    return merged_prs(_brain(args), args.since, args.repo), 0


def _cmd_validate(args):
    result = validate(_brain(args), args.paths or None, args.base)
    return result, 1 if result["errors"] else 0


def _cmd_review(args):
    return review(_brain(args), args.base, args.confidence or (), noise_holds=not args.no_noise), 0


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
    if args.action in ("start", "cleanup"):
        repo = workspace.repo_root(Path.cwd())
        if args.action == "cleanup":
            if not args.worktree:
                raise UsageError("pb routine cleanup needs --worktree")
            return gitops.routine_cleanup(repo, args.worktree), 0
        if not args.branch:
            raise UsageError("pb routine start needs --branch")
        return gitops.routine_start(repo, args.branch, args.worktree), 0
    brain = _brain(args)
    if args.action == "discard":
        return gitops.routine_discard(brain), 0
    if not args.branch:
        raise UsageError(f"pb routine {args.action} needs --branch")
    if not args.message:
        raise UsageError("pb routine finish needs -m MESSAGE")
    result = gitops.routine_finish(brain, args.branch, args.message, args.confidence or ())
    return result, 1 if result["conflict"] else 0


def _cmd_workspace(args):
    return workspace.sync(workspace.repo_root(Path.cwd())), 0


def _cmd_save(args):
    repo = workspace.repo_root(Path.cwd())
    if args.cont:
        result = workspace.save_continue(repo)
    else:
        if not args.message:
            raise UsageError("pb save needs -m MESSAGE")
        result = workspace.save(repo, args.message, args.paths, force_review=args.force_review)
    return result, 1 if (result["conflict"] or result["errors"]) else 0


def _repo_arg(args):
    if args.repo:
        return Path(args.repo)
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(proc.stdout.strip()) if proc.returncode == 0 else Path.cwd()


def _cmd_scan(args):
    return scan(_repo_arg(args)), 0


def _cmd_scaffold(args):
    if args.upgrade:
        return upgrade(_repo_arg(args)), 0
    if not args.product:
        raise UsageError("pb scaffold needs --product NAME")
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
    p = sub.add_parser("prs")
    p.add_argument("--since", required=True, help="ISO datetime cursor, e.g. 2026-10-30T02:00:00Z")
    p.add_argument("--repo", help="owner/name; default: github.repo in sources.md")
    p.set_defaults(handler=_cmd_prs)
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
    p.add_argument("--confidence", nargs="+", action="extend", metavar="PATH=LEVEL",
                   help="finish: pages written with less than high confidence (low, medium)")
    p.set_defaults(handler=_cmd_routine)
    p = sub.add_parser("review")
    p.add_argument("--base", default="HEAD", help="git commit to compare with (default: HEAD, uncommitted changes)")
    p.add_argument("--confidence", nargs="+", action="extend", metavar="PATH=LEVEL",
                   help="pages written with less than high confidence (low, medium)")
    p.add_argument("--no-noise", action="store_true", help="noise warnings never hold a page")
    p.set_defaults(handler=_cmd_review)
    p = sub.add_parser("scan")
    p.add_argument("--repo")
    p.set_defaults(handler=_cmd_scan)
    p = sub.add_parser("scaffold")
    p.add_argument("--repo")
    p.add_argument("--product")
    p.add_argument("--upgrade", action="store_true", help="existing brain: current workflows, plugin settings, toolkit")
    p.add_argument("--preset", default="software-product")
    p.set_defaults(handler=_cmd_scaffold)
    p = sub.add_parser("workspace")
    p.add_argument("action", choices=["sync"])
    p.set_defaults(handler=_cmd_workspace)
    p = sub.add_parser("save")
    p.add_argument("paths", nargs="*", help="the pages this save is about (default: every unsaved brain file)")
    p.add_argument("-m", "--message")
    p.add_argument("--continue", dest="cont", action="store_true", help="resume after resolving a conflict")
    p.add_argument("--force-review", action="store_true", help="configuration or toolkit changes: review PR only")
    p.set_defaults(handler=_cmd_save)
    sub.add_parser("toolkit-sync").set_defaults(handler=_cmd_toolkit_sync)
    p = sub.add_parser("lint")
    p.add_argument("--today")
    p.set_defaults(handler=_cmd_lint)
    p = sub.add_parser("validate")
    p.add_argument("paths", nargs="*")
    p.add_argument("--base", default="HEAD", help="git commit the noise checks compare with (default: HEAD)")
    p.set_defaults(handler=_cmd_validate)
    return parser
