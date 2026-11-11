"""Commit messages and PR titles in the format the repo's commit rules accept (.pb/schema/brain.md)."""
import re

from .brain import DEFAULTS
from .errors import UsageError

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
PR_TITLES = {"brain": "pr_title_brain", "init": "pr_title_init"}


def format_problem(fmt):
    """Why `commit_format` is unusable, or None."""
    if not isinstance(fmt, str):
        return "'commit_format' must be a string"
    names = set(PLACEHOLDER.findall(fmt))
    if "summary" not in names:
        return f"'{fmt}' has no {{summary}}: it is required"
    other = sorted(names - {"skill", "summary"})
    if other:
        return f"'{fmt}' uses {', '.join('{' + n + '}' for n in other)}: only {{skill}} and {{summary}} are allowed"
    return None


def _one_line(text):
    return " ".join(str(text or "").split())


def commit_message(brain, skill, summary):
    fmt = brain.config.get("commit_format")
    problem = format_problem(fmt)
    if problem:
        raise UsageError(f"commit_format in .pb/schema/brain.md: {problem}")
    summary = _one_line(summary)
    if not summary:
        raise UsageError("the commit summary (-m) is empty")
    return fmt.replace("{skill}", _one_line(skill) or "brain").replace("{summary}", summary)


def raw_message(message):
    """A message given in full (--raw), used verbatim."""
    if not str(message or "").strip():
        raise UsageError("the commit message (-m) is empty")
    return message


def compose(brain, skill, text, raw=False):
    return raw_message(text) if raw else commit_message(brain, skill, text)


def pr_title(brain, which):
    if which not in PR_TITLES:
        raise UsageError(f"no PR title '{which}': use one of {', '.join(PR_TITLES)}")
    key = PR_TITLES[which]
    return _one_line(brain.config.get(key)) or DEFAULTS[key]
