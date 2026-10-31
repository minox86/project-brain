"""Secret patterns that must never reach the brain."""
import re

PATTERNS = [
    ("aws", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe", re.compile(r"\b[rs]k_live_[0-9A-Za-z]{16,}")),
    ("llm-api-key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("azure-account-key", re.compile(r"(?i)AccountKey=[A-Za-z0-9+/=]{20,}")),
    ("bearer", re.compile(r"(?i)\bAuthorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url-credentials", re.compile(r"[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/${}<>]{3,}@")),
]

# A credential-like key (also inside identifiers: DB_PASSWORD, aws_secret_access_key), an optional
# closing quote (JSON), then `:` or `=` and the value.
ASSIGNMENT = re.compile(
    r"(?i)(?<![a-z])(secret[_-]?access[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|api[_-]?key"
    r"|access[_-]?key|password|passwd|pwd|secret)[\"']?\s*[:=]\s*[\"']?([^\s\"',;]+)")
KEBAB_WORDS = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[a-z]+)+$")


def _looks_like_secret(value):
    """Token-like value: not a placeholder, not prose; letters and digits, or long and space-free."""
    if any(c in value for c in "${}<>") or KEBAB_WORDS.match(value):
        return False
    has_letter = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return (len(value) >= 8 and has_letter and has_digit) or (len(value) >= 20 and has_letter)


def scan(text):
    """[{"line", "kind"}] for every line matching a secret pattern."""
    found = []
    for lineno, line in enumerate((text or "").splitlines(), 1):
        kind = next((k for k, pattern in PATTERNS if pattern.search(line)), None)
        if kind is None and any(_looks_like_secret(m.group(2)) for m in ASSIGNMENT.finditer(line)):
            kind = "assignment"
        if kind:
            found.append({"line": lineno, "kind": kind})
    return found
