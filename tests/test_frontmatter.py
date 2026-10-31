import unittest

import helpers  # noqa: F401
from pb_core import frontmatter as fm
from pb_core.errors import FrontmatterError


def doc(meta, body="body\n"):
    return "---\n" + meta + "\n---\n" + body


class FrontmatterTest(unittest.TestCase):
    def test_scalars(self):
        meta, body = fm.parse(doc('a: 1\nb: 1.5\nc: true\nd: null\ne: "x: y"\nf: plain text\ng: 2026-10-31'))
        self.assertEqual(meta, {"a": 1, "b": 1.5, "c": True, "d": None, "e": "x: y", "f": "plain text", "g": "2026-10-31"})
        self.assertEqual(body, "body\n")

    def test_inline_list_and_map(self):
        meta, _ = fm.parse(doc(
            "tags: [a, \"b, c\", 3]\n"
            "fields:\n"
            "  modules: {kind: list, of: link, to: module}\n"
            "  status: {kind: enum, values: [idea, planned], default: idea}\n"
        ))
        self.assertEqual(meta["tags"], ["a", "b, c", 3])
        self.assertEqual(meta["fields"]["modules"], {"kind": "list", "of": "link", "to": "module"})
        self.assertEqual(meta["fields"]["status"]["values"], ["idea", "planned"])

    def test_block_list_of_inline_maps(self):
        meta, _ = fm.parse(doc('teams:\n  - {id: a, channel: "Gen, eral"}\n  - {id: b, channel: X}\npaths:\n  - apps/web/**\n'))
        self.assertEqual(meta["teams"], [{"id": "a", "channel": "Gen, eral"}, {"id": "b", "channel": "X"}])
        self.assertEqual(meta["paths"], ["apps/web/**"])

    def test_wikilink_bare_value(self):
        meta, _ = fm.parse(doc('supersedes: [[Old Decision]]\naffects: ["[[A]]", "[[B]]"]'))
        self.assertEqual(meta["supersedes"], "[[Old Decision]]")
        self.assertEqual(meta["affects"], ["[[A]]", "[[B]]"])

    def test_crlf_and_bom(self):
        lf = doc("a: [x, y]\nb: text", "line1\nline2\n")
        crlf = "﻿" + lf.replace("\n", "\r\n")
        self.assertEqual(fm.parse(lf), fm.parse(crlf))

    def test_bare_top_level_string_with_commas(self):
        meta, _ = fm.parse(doc("summary: Approves invoices, then posts them"))
        self.assertEqual(meta["summary"], "Approves invoices, then posts them")

    def test_unclosed_frontmatter_raises(self):
        with self.assertRaises(FrontmatterError):
            fm.parse("---\na: 1\nbody")

    def test_no_frontmatter_returns_none(self):
        self.assertEqual(fm.parse("# Title\n"), (None, "# Title\n"))

    def test_comment_stripping(self):
        meta, _ = fm.parse(doc('# comment\na: b # c\nd: "b # c"\ne: x#y'))
        self.assertEqual(meta, {"a": "b", "d": "b # c", "e": "x#y"})

    def test_bad_line_raises_with_line_number(self):
        with self.assertRaises(FrontmatterError) as ctx:
            fm.parse(doc("a: 1\njust text"))
        self.assertIn("line 2", str(ctx.exception))

    def test_unbalanced_inline_raises(self):
        with self.assertRaises(FrontmatterError):
            fm.parse(doc("a: [x, y"))


if __name__ == "__main__":
    unittest.main()
