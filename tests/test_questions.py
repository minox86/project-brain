import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from helpers import ROOT, make_brain, page, files_of, run_cli

CONFIG = 'questions: {team: Product, team_id: "t-1", channel: Brain questions, channel_id: "19:abc@thread.tacv2"%s}'
QUESTION = ("Can an invoice be approved twice?\n\n## Why it matters\nBlocks the [approval](../functional/features/"
            "Approval.md) rules.^[jira:FIN-1]\n\n## Known so far\n- Finance says no.\n- The code allows it.\n")


def sources(extra=""):
    return {".pb/schema/sources.md": "---\n" + CONFIG % extra + "\n---\n# Sources\n"}


class Webhook:
    """A local stand-in for the Teams workflow: records every card posted to it."""

    def __init__(self, status=202):
        received = self.received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(status)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/workflows/x?sig=s3cr3tvalue"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def texts(payload):
    return [b.get("text") for b in payload["attachments"][0]["content"]["body"] if b.get("type") == "TextBlock"]


class QuestionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hook = Webhook()
        self.addCleanup(self.hook.close)
        patch = mock.patch.dict(os.environ, {"PB_QUESTIONS_WEBHOOK": self.hook.url})
        patch.start()
        self.addCleanup(patch.stop)

    def brain(self, *pages, extra="", config=True):
        files = files_of(*pages)
        files.update(sources(extra) if config else {})
        self.repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name), files)
        return self.repo

    def cli(self, *args):
        return run_cli("questions", *args, cwd=self.repo)

    def state(self):
        path = self.repo / "brain/.pb/state/questions.json"
        return json.loads(path.read_text())["posted"] if path.is_file() else {}

    def test_off_without_configuration(self):
        self.brain(page("open-question", "Twice", "area: functional"), config=False)
        code, data, _ = self.cli("publish")
        self.assertEqual((code, data["configured"], data["published"]), (0, False, []))
        self.assertEqual(self.hook.received, [])
        self.assertEqual(self.cli()[1], {"configured": False, "posted": [], "unpublished": 0})

    def test_publishes_each_open_question_once(self):
        self.brain(page("open-question", "Twice", "area: functional\ncreated: 2026-11-01", QUESTION),
                   page("open-question", "Closed", "area: technical\nstatus: resolved"),
                   page("open-question", "Older", "area: technical\ncreated: 2026-10-01"))
        code, data, err = self.cli("publish")
        self.assertEqual(code, 0, err)
        self.assertEqual(data["published"], ["Older", "Twice"])
        self.assertEqual((data["left"], data["failed"], data["webhook"]), (0, [], "$PB_QUESTIONS_WEBHOOK"))
        self.assertEqual(len(self.hook.received), 2)
        self.assertEqual(sorted(self.state()), ["Older", "Twice"])
        self.assertIsNone(self.state()["Twice"]["message_id"])
        code, data, _ = self.cli("publish")
        self.assertEqual((code, data["published"]), (0, []))
        self.assertEqual(len(self.hook.received), 2)

    def test_card_reads_as_title_question_sections_and_who_can_answer(self):
        self.brain(page("open-question", "Twice", "area: functional\naffects: [Approval]", QUESTION),
                   page("feature", "Approval"))
        self.cli("publish")
        payload = self.hook.received[0]
        self.assertEqual(payload["type"], "message")
        attachment = payload["attachments"][0]
        self.assertEqual(attachment["contentType"], "application/vnd.microsoft.card.adaptive")
        content = attachment["content"]
        self.assertEqual(content["type"], "AdaptiveCard")
        shown = texts(payload)
        self.assertEqual(shown, ["OPEN QUESTION · FUNCTIONAL", "Twice", "Can an invoice be approved twice?",
                                 "Why it matters", "Blocks the approval rules.", "Known so far",
                                 "- Finance says no.\n- The code allows it.", "Affects: Approval",
                                 "For: **Product**, **Analyst**"])
        # Nothing but text: no box on how to answer, no link to GitHub, nobody tagged without `people`.
        self.assertEqual({b["type"] for b in content["body"]}, {"TextBlock"})
        self.assertNotIn("actions", content)
        self.assertEqual(content["msteams"], {"width": "Full"})
        self.assertNotIn("github.com", json.dumps(payload))

    def test_card_names_the_roles_of_the_area_and_tags_their_people(self):
        people = (', people: {tech: [mario.rossi@acme.com], product: [{name: Anna B., email: anna@acme.com}], '
                  'analyst: [anna@acme.com, luca-de.santis@acme.com], ux: [ugo@acme.com]}')
        self.brain(page("open-question", "T", "area: technical\ncreated: 2026-11-01"),
                   page("open-question", "F", "area: functional\ncreated: 2026-11-02"),
                   page("open-question", "U", "area: ux\ncreated: 2026-11-03"), extra=people)
        self.assertEqual(self.cli("publish")[1]["published"], ["T", "F", "U"])
        tech, functional, ux = [p["attachments"][0]["content"] for p in self.hook.received]
        self.assertEqual(tech["body"][-1]["text"], "For: **Tech** · <at>Mario Rossi</at>")
        self.assertEqual(tech["msteams"]["entities"], [{
            "type": "mention", "text": "<at>Mario Rossi</at>",
            "mentioned": {"id": "mario.rossi@acme.com", "name": "Mario Rossi"}}])
        # Someone covering two roles is tagged once.
        self.assertEqual(functional["body"][-1]["text"],
                         "For: **Product**, **Analyst** · <at>Anna B.</at> <at>Luca De Santis</at>")
        self.assertEqual([e["mentioned"]["id"] for e in functional["msteams"]["entities"]],
                         ["anna@acme.com", "luca-de.santis@acme.com"])
        self.assertEqual(ux["body"][-1]["text"], "For: **UX** · <at>Ugo</at>")

    def test_areas_are_configurable(self):
        self.brain(page("open-question", "F", "area: functional"), page("open-question", "T", "area: technical"),
                   extra=", areas: [technical]")
        _, data, _ = self.cli("publish")
        self.assertEqual(data["published"], ["T"])

    def test_max_per_run_posts_the_oldest_and_leaves_the_rest(self):
        self.brain(*[page("open-question", f"Q{i}", f"area: ux\ncreated: 2026-11-0{i}") for i in range(1, 5)],
                   extra=", max_per_run: 2")
        _, data, _ = self.cli("publish")
        self.assertEqual((data["published"], data["left"]), (["Q1", "Q2"], 2))
        _, data, _ = self.cli("publish")
        self.assertEqual((data["published"], data["left"]), (["Q3", "Q4"], 0))

    def test_check_posts_nothing(self):
        self.brain(page("open-question", "Twice", "area: functional"))
        code, data, _ = self.cli("publish", "--check")
        self.assertEqual((code, data["would_publish"], data["published"]), (0, ["Twice"], []))
        self.assertEqual((self.hook.received, self.state()), ([], {}))

    def test_without_a_webhook_nothing_is_posted_and_nothing_fails(self):
        self.brain(page("open-question", "Twice", "area: functional"))
        with mock.patch.dict(os.environ, {"PB_QUESTIONS_WEBHOOK": ""}):
            code, data, _ = self.cli("publish")
        self.assertEqual((code, data["published"], data["left"], data["webhook"]), (0, [], 1, None))
        self.assertIn("no webhook", data["skipped"])
        self.assertEqual(self.state(), {})

    def test_webhook_from_the_clone_git_config_and_a_named_variable(self):
        self.brain(page("open-question", "Twice", "area: functional"), extra=", webhook_env: TEAM_HOOK")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "--local", "pb.questionsWebhook", self.hook.url], cwd=self.repo, check=True)
        code, data, _ = self.cli("publish", "--check")
        self.assertEqual(data["webhook"], "git config pb.questionsWebhook")  # PB_QUESTIONS_WEBHOOK is not its name
        with mock.patch.dict(os.environ, {"TEAM_HOOK": self.hook.url}):
            self.assertEqual(self.cli("publish")[1]["webhook"], "$TEAM_HOOK")
        self.assertEqual(len(self.hook.received), 1)

    def test_a_refused_card_is_reported_without_the_url_and_retried_later(self):
        failing = Webhook(status=400)
        self.addCleanup(failing.close)
        self.brain(page("open-question", "Twice", "area: functional"))
        with mock.patch.dict(os.environ, {"PB_QUESTIONS_WEBHOOK": failing.url}):
            code, data, err = self.cli("publish")
        self.assertEqual(code, 1)
        self.assertEqual(data["failed"][0]["title"], "Twice")
        self.assertIn("400", data["failed"][0]["error"])
        self.assertNotIn("s3cr3tvalue", json.dumps(data) + err)
        self.assertEqual(self.state(), {})
        self.assertEqual(self.cli("publish")[1]["published"], ["Twice"])

    def test_an_unreachable_webhook_never_shows_the_url(self):
        self.brain(page("open-question", "Twice", "area: functional"))
        with mock.patch.dict(os.environ, {"PB_QUESTIONS_WEBHOOK": "http://127.0.0.1:9/hook?sig=s3cr3tvalue"}):
            code, data, err = self.cli("publish")
        self.assertEqual(code, 1)
        self.assertIn("could not reach 127.0.0.1", data["failed"][0]["error"])
        self.assertNotIn("s3cr3tvalue", json.dumps(data) + err)

    def test_status_mark_and_forgetting_answered_questions(self):
        self.brain(page("open-question", "Twice", "area: functional"), page("open-question", "Later", "area: ux"))
        self.cli("publish")
        code, data, _ = self.cli("mark", "Twice", "--message", "170000", "--seen", "2026-11-16T10:00:00Z")
        self.assertEqual((code, data["marked"]["message_id"], data["marked"]["seen"]),
                         (0, "170000", "2026-11-16T10:00:00Z"))
        _, data, _ = self.cli()
        self.assertEqual(data["channel"], {"team": "Product", "team_id": "t-1", "channel": "Brain questions",
                                           "channel_id": "19:abc@thread.tacv2"})
        by_title = {q["title"]: q for q in data["posted"]}
        self.assertEqual((by_title["Twice"]["message_id"], by_title["Twice"]["path"]),
                         ("170000", "open-questions/Twice.md"))
        self.assertEqual(data["unpublished"], 0)
        self.assertEqual(self.cli("mark", "Unknown", "--message", "1")[0], 2)
        (self.repo / "brain/open-questions/Twice.md").unlink()  # answered: the routine deleted the page
        _, data, _ = self.cli("publish")
        self.assertEqual(data["forgotten"], ["Twice"])
        self.assertEqual(sorted(self.state()), ["Later"])

    def italian(self, *pages, extra=""):
        self.brain(*pages, extra=extra)
        path = self.repo / "brain/.pb/schema/brain.md"
        path.write_text(path.read_text().replace("team_language: en", "team_language: it"))

    def translations(self, data):
        path = os.path.join(self.tmp.name, "translations.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def test_cards_are_in_english_by_default(self):
        self.brain(page("open-question", "Twice", "area: functional"))
        _, data, _ = self.cli("publish", "--check")
        self.assertEqual(data["language"], "en")
        self.assertNotIn("translate", data)

    def test_another_team_language_asks_for_the_translation_and_posts_it(self):
        self.italian(page("open-question", "Twice", "area: functional\naffects: [Approval]", QUESTION),
                     page("feature", "Approval"))
        _, data, _ = self.cli("publish", "--check")
        self.assertEqual(data["language"], "it")
        self.assertEqual(data["translate"]["questions"], {"Twice": {
            "title": "Twice", "question": "Can an invoice be approved twice?",
            "sections": [{"heading": "Why it matters", "text": "Blocks the approval rules."},
                         {"heading": "Known so far", "text": "- Finance says no.\n- The code allows it."}]}})
        self.assertEqual(data["translate"]["labels"]["open_question"], "OPEN QUESTION")
        path = self.translations({
            "labels": {"open_question": "DOMANDA APERTA", "functional": "FUNZIONALE", "affects": "Riguarda",
                       "for": "Per", "colour": "ignored"},
            "questions": {"Twice": {"title": "Due volte", "question": "Una fattura può essere approvata due volte?",
                                    "sections": [{"heading": "Perché conta", "text": "Blocca le regole."}]}}})
        code, data, err = self.cli("publish", "--translations", path)
        self.assertEqual(code, 0, err)
        self.assertEqual((data["published"], data["untranslated"]), (["Twice"], []))
        self.assertEqual(texts(self.hook.received[0]), [
            "DOMANDA APERTA · FUNZIONALE", "Due volte", "Una fattura può essere approvata due volte?",
            "Perché conta", "Blocca le regole.", "Riguarda: Approval", "Per: **Product**, **Analyst**"])
        # The brain keeps the English title; the state remembers what the card shows, to find it in the channel.
        self.assertEqual(self.state()["Twice"]["shown"], "Due volte")
        self.assertEqual(self.cli()[1]["posted"][0]["shown"], "Due volte")
        self.assertTrue((self.repo / "brain/open-questions/Twice.md").is_file())

    def test_a_question_without_translation_waits(self):
        self.italian(page("open-question", "A", "area: ux\ncreated: 2026-11-01"),
                     page("open-question", "B", "area: ux\ncreated: 2026-11-02"))
        code, data, _ = self.cli("publish")
        self.assertEqual((code, data["published"], data["untranslated"], data["left"]), (0, [], ["A", "B"], 2))
        self.assertEqual(self.hook.received, [])
        path = self.translations({"questions": {"B": {"title": "Bi"}}})
        _, data, _ = self.cli("publish", "--translations", path)
        self.assertEqual((data["published"], data["untranslated"], data["left"]), (["B"], ["A"], 1))
        self.assertEqual(self.cli("publish", "--translations", self.translations({"questions": {"A": {}}}))[0], 2)

    def test_team_language_is_validated(self):
        self.italian()
        self.assertEqual(run_cli("validate", cwd=self.repo)[1]["errors"], [])
        path = self.repo / "brain/.pb/schema/brain.md"
        path.write_text(path.read_text().replace("team_language: it", "team_language: the language of Dante"))
        self.assertEqual([e["code"] for e in run_cli("validate", cwd=self.repo)[1]["errors"]], ["bad-team-language"])

    def test_init_asks_the_team_language_and_the_brain_stays_english(self):
        init = (ROOT / "skills/init/SKILL.md").read_text()
        self.assertIn("`team_language`", init)
        self.assertIn("Default **English** (`en`)", init)
        self.assertIn("team_language: en", (ROOT / "presets/software-product/brain.md").read_text())
        sync = (ROOT / "skills/sync/SKILL.md").read_text()
        self.assertIn("PB questions publish --translations <file>", sync)
        self.assertIn("never translated in the brain", sync)

    def test_switched_off_nothing_is_posted_until_it_is_switched_on_again(self):
        self.brain(page("open-question", "Twice", "area: functional"), extra="}\ndisabled: [questions")
        path = self.repo / "brain/.pb/schema/sources.md"
        path.write_text(path.read_text().replace("[questions}", "[questions]"))
        for args in (("publish",), ("publish", "--check")):
            code, data, err = self.cli(*args)
            self.assertEqual((code, data["off"], data["published"]), (0, True, []), err)
            self.assertIn("switched off", data["skipped"])
        self.assertEqual((self.hook.received, self.state()), ([], {}))
        self.assertTrue(self.cli()[1]["off"])
        self.assertEqual(run_cli("sources", "on", "questions", cwd=self.repo)[0], 0)
        code, data, _ = self.cli("publish")
        self.assertEqual((data["off"], data["published"]), (False, ["Twice"]))
        self.assertEqual(len(self.hook.received), 1)

    def test_test_card(self):
        self.brain()
        code, data, _ = self.cli("test")
        self.assertEqual((code, data["posted"]), (0, True))
        self.assertIn("The Product brain can post here", texts(self.hook.received[0]))
        with mock.patch.dict(os.environ, {"PB_QUESTIONS_WEBHOOK": ""}):
            self.assertEqual(self.cli("test")[0], 2)


class QuestionsSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def errors(self, frontmatter):
        repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name),
                          {".pb/schema/sources.md": f"---\n{frontmatter}\n---\n# Sources\n"})
        return [(e["code"], e["message"]) for e in run_cli("validate", cwd=repo)[1]["errors"]]

    def test_valid_settings_and_off(self):
        self.assertEqual(self.errors(CONFIG % ", max_per_run: 3, areas: [functional, ux], "
                                              "people: {tech: [a@b.c], ux: [{name: U, email: u@b.c}]}"), [])
        self.assertIn("unknown key 'reply_hint'", self.errors(CONFIG % ', reply_hint: "x"')[0][1])
        self.assertEqual(self.errors("questions: null"), [])

    def test_bad_settings(self):
        found = self.errors("questions: {team: Product, max_per_run: 0, areas: [legal], colour: red, "
                            "people: {qa: [a@b.c], tech: [Mario Rossi]}}")
        self.assertEqual({code for code, _ in found}, {"bad-questions"})
        text = " ".join(message for _, message in found)
        for part in ("team_id is missing", "channel_id is missing", "max_per_run", "areas", "unknown key 'colour'",
                     "unknown role 'qa'", "people.tech must be a list of Teams sign-in addresses"):
            self.assertIn(part, text)

    def test_a_webhook_url_in_the_repo_is_an_error(self):
        url = "https://prod-12.westeurope.logic.azure.com:443/workflows/abc/triggers/manual/paths/invoke?sig=AbCdEf123456"
        found = self.errors((CONFIG % f', webhook_env: "{url}"'))
        self.assertIn("secret", {code for code, _ in found})
        self.assertTrue(any("never goes in the repo" in message for _, message in found), found)
        repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name),
                          files_of(page("open-question", "Hook", "area: technical", f"Post to {url} ?\n")))
        self.assertIn("secret", [e["code"] for e in run_cli("validate", cwd=repo)[1]["errors"]])

    def test_preset_documents_the_setting(self):
        text = (ROOT / "presets/software-product/sources.md").read_text()
        self.assertIn("questions: null", text)
        self.assertIn("never written here", text)


if __name__ == "__main__":
    unittest.main()
