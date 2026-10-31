"""Secret patterns that must never reach the brain."""
import re

PATTERNS = [
    ("aws", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url-credentials", re.compile(r"[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/]{3,}@")),
    ("assignment", re.compile(
        r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b"
        r"\s*[:=]\s*[\"']?[^\s\"'<>${}]{8,}")),
]


def scan(text):
    """[{"line", "kind"}] for every line matching a secret pattern."""
    found = []
    for lineno, line in enumerate((text or "").splitlines(), 1):
        for kind, pattern in PATTERNS:
            if pattern.search(line):
                found.append({"line": lineno, "kind": kind})
                break
    return found
