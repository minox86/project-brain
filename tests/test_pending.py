import datetime
import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli

from pb_core import pending
from pb_core.brain import Brain

OPEN = "- [ ] R1 · functional · DUPLICATE · Invoice, Bill · same concept? · suggested: merge into Invoice · found: 2026-11-08"
KEPT = "- [x] R2 · technical · MOVED · Billing · retry rule sits on the feature · suggested: none · found: 2026-11-08 · kept: on purpose"
BAD = "- [ ] R3 · finance · DUPLICATE · A, B · x"


class PendingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def repo(self, files=None):
        return make_brain(self.tmp.name, files)

    def test_reads_open_ticked_and_malformed_lines(self):
        repo = self.repo({".pb/pending.md": f"# Pending\n\nprose - [ ] not a line\n{OPEN}\n{KEPT}\n{BAD}\n"})
        found = pending.read(Brain(repo / "brain"))
        self.assertEqual([(i["n"], i["done"], i["area"], i["tag"]) for i in found["items"]],
                         [(1, False, "functional", "DUPLICATE"), (2, True, "technical", "MOVED")])
        self.assertEqual(found["bad"], [{"line": 6, "text": BAD, "why": "not a queue line"}])

    def test_no_file_means_nothing_waits_and_no_line(self):
        counts = pending.waiting(Brain(self.repo() / "brain"))
        self.assertEqual(counts, {"functional": 0, "technical": 0, "any": 0, "total": 0, "report": None})
        self.assertEqual(pending.pr_line(counts), "")

    def test_waiting_counts_open_lines_and_open_questions_by_competence(self):
        repo = self.repo({
            ".pb/pending.md": f"{OPEN}\n{KEPT}\n{BAD}\n",
            ".pb/digests/2026-11-01-review.md": "old", ".pb/digests/2026-11-08-review.md": "new",
            ".pb/digests/2026-11-09.md": "nightly",
            **files_of(page("open-question", "Ux", "area: ux"), page("open-question", "Tech", "area: technical"),
                       page("open-question", "No area"), page("open-question", "Closed", "area: ux\nstatus: resolved")),
        })
        counts = pending.waiting(Brain(repo / "brain"))
        self.assertEqual(counts, {"functional": 2, "technical": 1, "any": 1, "total": 4,
                                  "report": "brain/.pb/digests/2026-11-08-review.md"})
        self.assertEqual(pending.pr_line(counts), "Waiting for a decision (run `/pb:review`): functional 2, "
                         "technical 1, any 1. Latest review report: `brain/.pb/digests/2026-11-08-review.md`.")

    def test_cli_adds_with_the_next_number_and_refuses_unknown_area_or_tag(self):
        repo = self.repo({".pb/pending.md": f"{OPEN}\n{KEPT}\n"})
        entry = "any · GLOSSARY · Ledger · used on 3 pages with no concept · suggested: create the concept"
        code, data, _ = run_cli("pending", "--add", entry, "--today", "2026-11-13", cwd=repo)
        self.assertEqual((code, data["added"]["n"]), (0, 3), data)
        text = (repo / "brain/.pb/pending.md").read_text()
        self.assertEqual(text.splitlines()[-1], f"- [ ] R3 · {entry} · found: 2026-11-13")
        self.assertTrue(text.startswith("<!-- last: R3 -->\n\n" + OPEN), text)
        self.assertEqual(data["waiting"]["any"], 1)
        for wrong in ("finance · GLOSSARY · A · x", "any · TYPO · A · x", "any · GLOSSARY"):
            self.assertEqual(run_cli("pending", "--add", wrong, cwd=repo)[0], 2, wrong)

    def test_first_add_creates_the_file(self):
        repo = self.repo()
        run_cli("pending", "--add", "technical · LINK · Billing · which page is meant?", "--today", "2026-11-13", cwd=repo)
        text = (repo / "brain/.pb/pending.md").read_text()
        self.assertTrue(text.startswith("# Pending review items"))
        self.assertEqual(run_cli("validate", cwd=repo)[0], 0)

    def test_a_no_stays_ticked_and_an_answer_removes_the_line(self):
        repo = self.repo({".pb/pending.md": f"{OPEN}\n{KEPT}\n"})
        code, data, _ = run_cli("pending", "--done", "1", "--kept", "two different documents", cwd=repo)
        self.assertEqual(code, 0, data)
        self.assertIn(OPEN.replace("- [ ]", "- [x]") + " · kept: two different documents",
                      (repo / "brain/.pb/pending.md").read_text())
        self.assertEqual(data["waiting"]["functional"], 0)
        run_cli("pending", "--remove", "2", cwd=repo)
        self.assertNotIn("] R2", (repo / "brain/.pb/pending.md").read_text())
        self.assertEqual(run_cli("pending", "--remove", "9", cwd=repo)[0], 2)
        self.assertEqual(run_cli("pending", "--done", "1", cwd=repo)[0], 2)

    def test_numbers_are_never_shared(self):
        twin = OPEN.replace("Invoice, Bill", "Order, Purchase")
        repo = self.repo({".pb/pending.md": f"{OPEN}\n<<<<<<< HEAD\n{twin}\n=======\n- [ ] R7 · nobody · LINK · A · x\n"})
        found = pending.read(Brain(repo / "brain"))
        self.assertEqual([i["n"] for i in found["items"]], [1])
        self.assertEqual([b["why"] for b in found["bad"]],
                         ["a merge conflict marker", "R1 is used twice", "a merge conflict marker", "not a queue line"])
        _, data, _ = run_cli("pending", "--add", "any · LINK · A · which page?", cwd=repo)
        self.assertEqual(data["added"]["n"], 8)  # past the malformed R7 too

    def test_cli_refuses_before_writing(self):
        repo = self.repo({".pb/pending.md": f"{OPEN}\n{KEPT}\n"})
        before = (repo / "brain/.pb/pending.md").read_text()
        for args in (("--add", "any · LINK · A · x", "--done", "1"), ("--done", "1", "--kept", "r", "--remove", "2"),
                     ("--done", "2", "--kept", "again")):
            self.assertEqual(run_cli("pending", *args, cwd=repo)[0], 2, args)
        self.assertEqual((repo / "brain/.pb/pending.md").read_text(), before)

    def test_merge_keeps_both_sides_answers_and_ticks(self):
        line = lambda n, pages, done=" ", tail="": f"- [{done}] R{n} · functional · DUPLICATE · {pages} · same? · suggested: merge · found: 2026-11-01{tail}"
        base = "# Pending\n\n" + "\n".join([line(1, "A, B"), line(2, "C, D"), line(3, "E, F")]) + "\n"
        routine = base + line(4, "G, H") + "\n"                                  # the weekly run queued one more
        owner = "# Pending\n\n" + "\n".join([line(2, "C, D", "x", " · kept: different things"),   # answered R1, ticked R2
                                               line(3, "E, F"), line(4, "I, L")]) + "\n"           # and queued their own R4
        merged = pending.merge_texts(base, routine, owner)
        self.assertEqual(merged, "# Pending\n\n<!-- last: R5 -->\n\n" + "\n".join([
            line(2, "C, D", "x", " · kept: different things"), line(3, "E, F"), line(4, "G, H"), line(5, "I, L")]) + "\n")
        self.assertEqual(pending._parse(merged)[1], [])
        self.assertEqual(pending.merge_texts(None, None, owner), owner.replace("\n\n", "\n\n<!-- last: R4 -->\n\n", 1))

    def test_merge_never_gives_a_number_either_side_already_gave(self):
        line = lambda n, pages: f"- [ ] R{n} · any · LINK · {pages} · which? · suggested: none · found: 2026-11-01"
        base = "# Pending\n\n<!-- last: R2 -->\n\n" + line(1, "A") + "\n"
        routine = "# Pending\n\n<!-- last: R3 -->\n\n" + line(1, "A") + "\n" + line(3, "B") + "\n"
        owner = "# Pending\n\n<!-- last: R6 -->\n\n" + line(3, "C") + "\n"   # answered R1; gave and settled R4-R6
        self.assertEqual(pending.merge_texts(base, routine, owner),
                         "# Pending\n\n<!-- last: R7 -->\n\n" + line(3, "B") + "\n" + line(7, "C") + "\n")

    def test_a_number_is_never_given_twice(self):
        repo = self.repo({".pb/pending.md": f"# Pending\n\n{OPEN}\n{KEPT}\n"})   # a queue written before the note
        add = lambda: run_cli("pending", "--add", "any · LINK · A · which page?", cwd=repo)[1]["added"]["n"]
        run_cli("pending", "--remove", "2", cwd=repo)
        self.assertEqual(add(), 3)   # not R2 again
        run_cli("pending", "--remove", "3", cwd=repo)
        run_cli("pending", "--done", "1", "--kept", "two documents", cwd=repo)
        self.assertEqual(add(), 4)
        text = (repo / "brain/.pb/pending.md").read_text()
        self.assertEqual(text.count("<!-- last:"), 1)
        self.assertIn("# Pending\n\n<!-- last: R4 -->\n\n- [x] R1", text)
        self.assertEqual(run_cli("validate", cwd=repo)[0], 0)

    def test_a_secret_in_the_queue_is_found_whatever_the_scope(self):
        leak = OPEN.replace("same concept?", "password: hunter2Xk9mQ7vLp3")
        repo = self.repo({".pb/pending.md": f"{leak}\n"})
        for args in ((), ("brain/AGENTS.md",)):
            code, data, _ = run_cli("validate", *args, cwd=repo)
            self.assertEqual([e["code"] for e in data["errors"] if e["path"] == ".pb/pending.md"], ["secret"], args)

    def test_validate_names_the_malformed_line_whatever_the_scope(self):
        repo = self.repo({".pb/pending.md": f"{OPEN}\n{BAD}\n"})
        code, data, _ = run_cli("validate", "brain/AGENTS.md", cwd=repo)
        self.assertEqual([e["code"] for e in data["errors"] if e["path"] == ".pb/pending.md"], ["bad-pending"])

    def test_validate_names_the_malformed_line(self):
        repo = self.repo({".pb/pending.md": f"{OPEN}\n{BAD}\n"})
        code, data, _ = run_cli("validate", cwd=repo)
        self.assertEqual(code, 1)
        self.assertEqual([(e["path"], e["code"]) for e in data["errors"]], [(".pb/pending.md", "bad-pending")])
        self.assertIn("line 2", data["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
