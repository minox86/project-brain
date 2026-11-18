import tempfile
import unittest

from helpers import ROOT, make_brain, run_cli

CONFIG = """---
routine: {branch: docs/brain, schedule: "0 2 * * *"}
teams:
  - {id: dev, team: Product, team_id: "t-1", channel: Dev, channel_id: "c-1"}
  - {id: design, team: Product, team_id: "t-1", channel: Design, channel_id: "c-2"}
confluence: []
github: {repo: acme/mono}
jira:
  - {id: fin, project: FIN}
meetings: []
questions: null
%s---
# Sources

Prose that stays.
"""


class TeamsThreadStateTest(unittest.TestCase):
    def test_channel_state_keeps_cursor_and_watched_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp)
            value = '{"cursor": "2026-11-18T09:00:00Z", "threads": {"1700000000001": "2026-11-17T16:30:00Z"}}'
            self.assertEqual(run_cli("state", "set", "teams", "dev", value, cwd=repo)[0], 0)
            data = run_cli("state", "get", "teams", "dev", cwd=repo)[1]
            self.assertEqual(data["value"]["threads"], {"1700000000001": "2026-11-17T16:30:00Z"})


class SourcesSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def brain(self, disabled=""):
        self.repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name), {".pb/schema/sources.md": CONFIG % disabled})
        return self.repo

    def cli(self, *args):
        return run_cli("sources", *args, cwd=self.repo)

    def text(self):
        return (self.repo / "brain/.pb/schema/sources.md").read_text()

    def test_everything_configured_is_read_by_default(self):
        self.brain()
        code, data, err = self.cli()
        self.assertEqual(code, 0, err)
        self.assertEqual((data["active"], data["off"]), (["teams", "github", "jira"], []))
        self.assertEqual(data["unconfigured"], ["confluence", "meetings", "questions"])
        self.assertEqual(data["entries"], {"teams": ["dev", "design"], "jira": ["fin"]})

    def test_switching_a_source_off_and_on_rewrites_only_the_switch(self):
        self.brain()
        code, data, err = self.cli("off", "jira", "github")
        self.assertEqual(code, 0, err)
        self.assertEqual((data["active"], data["off"]), (["teams"], ["github", "jira"]))
        self.assertIn("disabled: [jira, github]\n---\n# Sources\n\nProse that stays.\n", self.text())
        self.assertIn("  - {id: fin, project: FIN}", self.text())  # the configuration stays
        self.assertEqual(self.cli()[1]["off"], ["github", "jira"])
        self.assertEqual(run_cli("validate", cwd=self.repo)[1]["errors"], [])
        code, data, _ = self.cli("on", "jira")
        self.assertEqual((data["active"], data["off"]), (["teams", "jira"], ["github"]))
        self.assertEqual(self.text().count("disabled:"), 1)

    def test_one_entry_can_be_switched_off(self):
        self.brain()
        _, data, _ = self.cli("off", "teams/design")
        self.assertEqual((data["active"], data["off"]), (["teams", "github", "jira"], ["teams/design"]))
        self.assertEqual(data["entries"]["teams"], ["dev"])
        _, data, _ = self.cli("off", "teams/dev")  # every entry off: the source is not read
        self.assertEqual(data["active"], ["github", "jira"])
        _, data, _ = self.cli("on", "teams")  # the whole source on again clears its entries
        self.assertEqual((data["off"], data["disabled"]), ([], []))

    def test_a_block_list_written_by_hand_is_replaced(self):
        self.brain("disabled:\n  - jira\n  - teams/dev\n")
        self.assertEqual(self.cli()[1]["off"], ["teams/dev", "jira"])
        self.cli("on", "jira")
        self.assertIn("disabled: [teams/dev]\n---\n", self.text())
        self.assertNotIn("  - jira", self.text())

    def test_a_block_list_with_blank_lines_is_removed_whole(self):
        self.brain("disabled:\n  - jira\n\n  - teams/dev\n\n- github\n\n")
        self.assertEqual(self.cli()[1]["disabled"], ["jira", "teams/dev", "github"])
        code, data, err = self.cli("on", "jira")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.text().count("disabled:"), 1)
        self.assertIn("questions: null\ndisabled: [teams/dev, github]\n---\n", self.text())
        self.assertEqual(self.cli()[1]["disabled"], ["teams/dev", "github"])  # it loads again, nothing left behind
        self.assertEqual(run_cli("validate", cwd=self.repo)[1]["errors"], [])

    def test_a_switch_in_the_middle_keeps_the_keys_around_it(self):
        self.repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name), {".pb/schema/sources.md": (
            "---\ndisabled:\n  - jira\n\n  - github\n\njira:\n  - {id: fin, project: FIN}\n"
            "github: {repo: acme/mono}\n---\n# Sources\n")})
        _, data, _ = self.cli("on", "github")
        self.assertEqual((data["active"], data["off"]), (["github"], ["jira"]))
        self.assertEqual(self.text(), "---\n\njira:\n  - {id: fin, project: FIN}\ngithub: {repo: acme/mono}\n"
                                      "disabled: [jira]\n---\n# Sources\n")

    def test_unknown_names_are_refused(self):
        self.brain()
        for name in ("slack", "teams/nope", "github/x"):
            code, _, err = self.cli("off", name)
            self.assertEqual(code, 2, name)
        self.assertEqual(self.cli("off")[0], 2)
        self.assertNotIn("disabled", self.text())

    def test_validate_reports_a_bad_switch(self):
        self.brain("disabled: [slack, teams/nope]\n")
        errors = run_cli("validate", cwd=self.repo)[1]["errors"]
        self.assertEqual([e["code"] for e in errors], ["bad-disabled", "bad-disabled"])
        self.brain("disabled: jira\n")
        self.assertEqual([e["code"] for e in run_cli("validate", cwd=self.repo)[1]["errors"]], ["bad-disabled"])

    def test_instructions_follow_the_switch_and_ingest_teams_at_once(self):
        sync = (ROOT / "skills/sync/SKILL.md").read_text()
        reader = (ROOT / "references/reader.md").read_text()
        setup = (ROOT / "skills/routine-setup/SKILL.md").read_text()
        self.assertIn("disabled: []", (ROOT / "presets/software-product/sources.md").read_text())
        self.assertIn("`PB sources`", sync)
        self.assertIn("`PB sources`", (ROOT / "references/conventions.md").read_text())
        self.assertIn("$PB sources", (ROOT / "templates/routine/prompt.md").read_text())
        for part in ("## 6d. The switch", "PB sources off", "routine finish --branch docs/brain"):
            self.assertIn(part, setup)
        # Teams messages are ingested at the first run that sees them: only a meeting without transcript waits.
        self.assertIn("A Teams thread is never deferred", reader)
        self.assertIn("with no waiting time", sync)
        # Replies never come with the roots: the reader asks for them, also on threads older than the cursor,
        # and the state keeps the last-read point of each watched thread.
        for part in ("parentMessageId: <root id>", "created before the cursor", "its last-read point",
                     "Check the watched threads the walk did not reach", "THREADS <root message id=last-read point"):
            self.assertIn(part, reader)
        for part in ('"threads": {"<root message id>": "<ISO datetime>"}', "the reader's `THREADS`",
                     "`thread_watch_days`"):
            self.assertIn(part, sync)
        self.assertIn("thread_watch_days: 14", (ROOT / "presets/software-product/brain.md").read_text())
        for text in (sync, reader, setup):
            self.assertNotIn("less than 24 hours old", text)
            self.assertNotIn("active threads", text)


if __name__ == "__main__":
    unittest.main()
