"""Parser for the restricted YAML subset used in frontmatter.

Supported grammar:
- top-level `key: value` lines;
- `key:` followed by an indented block: a list (`- value`) or a one-level
  map (`sub: value`);
- values: quoted or bare strings, ints, floats, true/false, null/~, inline
  lists `[a, b]` and inline maps `{k: v}`, nestable;
- `#` comments at line start or after whitespace, outside quotes.
A bare value starting with `[[` is a string (wikilink). Dates stay strings.
"""
import re

from .errors import FrontmatterError

_INT = re.compile(r"-?\d+$")
_FLOAT = re.compile(r"-?\d+\.\d+$")


def split(text):
    """Separate frontmatter and body. Returns (frontmatter_text | None, body)."""
    text = text.replace("\r\n", "\n")
    if text.startswith("﻿"):
        text = text[1:]
    if not text.startswith("---\n"):
        return None, text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise FrontmatterError("unclosed frontmatter: missing '---' line")


def parse(text):
    """Returns (meta | None, body). meta is None when there is no frontmatter."""
    src, body = split(text)
    if src is None:
        return None, body
    return _parse_mapping(src), body


def _parse_mapping(src):
    result = {}
    lines = src.split("\n")
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i])
        if not line.strip():
            i += 1
            continue
        if line[0] in " \t":
            raise FrontmatterError(f"line {i + 1}: unexpected indentation")
        key, rest = _split_key(line, i + 1)
        i += 1
        if rest:
            result[key] = _value(rest, i)
            continue
        block = []
        while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t" or _is_item(lines[i])):
            stripped = _strip_comment(lines[i]).strip()
            if stripped:
                block.append((i + 1, stripped))
            i += 1
        result[key] = _parse_block(block)
    return result


def _is_item(line):
    return line.rstrip() == "-" or line.startswith("- ")


def _split_key(line, lineno):
    key, sep, rest = line.partition(":")
    key = key.strip()
    if not sep or not key or any(c in key for c in "[{\"'"):
        raise FrontmatterError(f"line {lineno}: expected 'key: value'")
    return key, rest.strip()


def _parse_block(block):
    if not block:
        return None
    if all(text == "-" or text.startswith("- ") for _, text in block):
        return [_value(text[1:].strip(), lineno) for lineno, text in block]
    result = {}
    for lineno, text in block:
        key, rest = _split_key(text, lineno)
        result[key] = _value(rest, lineno) if rest else None
    return result


def _value(text, lineno):
    try:
        return parse_value(text)
    except FrontmatterError as exc:
        raise FrontmatterError(f"line {lineno}: {exc}")


def _strip_comment(line):
    quote = None
    escaped = False
    for i, ch in enumerate(line):
        if quote:
            if escaped:
                escaped = False
                continue
            if ch == "\\" and quote == '"':
                escaped = True
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            if i == 0 or line[i - 1] in " \t[{,:":
                quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line


def parse_value(text):
    """Parse one value of the subset."""
    text = text.strip()
    if text.startswith("[[") and not text.startswith("[[["):
        return text
    if not text or text[0] not in "[{\"'":
        return _scalar(text)
    value, pos = _parse_inline(text, 0)
    if text[pos:].strip():
        raise FrontmatterError(f"unexpected text after value: {text[pos:].strip()!r}")
    return value


def _parse_inline(text, pos):
    pos = _skip_ws(text, pos)
    if pos >= len(text):
        return None, pos
    ch = text[pos]
    if ch == "[":
        return _parse_seq(text, pos + 1, "]", list)
    if ch == "{":
        return _parse_seq(text, pos + 1, "}", dict)
    if ch in "\"'":
        return _parse_quoted(text, pos)
    return _parse_bare(text, pos)


def _parse_seq(text, pos, close, kind):
    result = [] if kind is list else {}
    pos = _skip_ws(text, pos)
    if pos < len(text) and text[pos] == close:
        return result, pos + 1
    while True:
        if kind is dict:
            end = text.find(":", pos)
            if end < 0:
                raise FrontmatterError("expected 'key: value' in inline map")
            key = text[pos:end].strip()
            if not key:
                raise FrontmatterError("empty key in inline map")
            value, pos = _parse_inline(text, end + 1)
            result[key] = value
        else:
            if text.startswith("[[", _skip_ws(text, pos)):
                start = _skip_ws(text, pos)
                end = text.find("]]", start)
                if end < 0:
                    raise FrontmatterError("unclosed wikilink")
                value, pos = text[start:end + 2], end + 2
            else:
                value, pos = _parse_inline(text, pos)
            result.append(value)
        pos = _skip_ws(text, pos)
        if pos >= len(text):
            raise FrontmatterError(f"missing '{close}'")
        if text[pos] == ",":
            pos += 1
            continue
        if text[pos] == close:
            return result, pos + 1
        raise FrontmatterError(f"unexpected character {text[pos]!r}")


def _parse_quoted(text, pos):
    quote = text[pos]
    out = []
    i = pos + 1
    while i < len(text):
        ch = text[i]
        if quote == '"' and ch == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
            continue
        if ch == quote:
            if quote == "'" and text.startswith("''", i):
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise FrontmatterError("unclosed quoted string")


def _parse_bare(text, pos):
    i = pos
    while i < len(text) and text[i] not in ",]}":
        i += 1
    raw = text[pos:i].strip()
    return _scalar(raw), i


def _scalar(raw):
    if raw in ("", "null", "~"):
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if _INT.match(raw):
        return int(raw)
    if _FLOAT.match(raw):
        return float(raw)
    return raw


def _skip_ws(text, pos):
    while pos < len(text) and text[pos] in " \t":
        pos += 1
    return pos
