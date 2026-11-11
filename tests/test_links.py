import tempfile
import unittest

from helpers import files_of, make_brain, page, run_cli
from pb_core import links
from pb_core.brain import Brain

HEAD = "---\ntype: feature\ntitle: \"Approval\"\n---\n"


class NormaliseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def brain(self, body, extra=()):
        repo = make_brain(self.tmp.name, files_of(
            page("feature", "Approval", "", body),
            page("concept", "Association fact", "term_en: Association fact\naliases: [Fact]", "## Examples\nx\n"),
            page("concept", "Fattura elettronica è", "term_en: E-invoice"),
            page("module", "Billing", "paths: [a/**]", "## Pitfalls\nx\n"),
            *extra,
        ))
        return repo, Brain(repo / "brain")

    def normalised(self, body, extra=()):
        repo, brain = self.brain(body, extra)
        changed = links.normalise(brain)
        return (repo / "brain/functional/features/Approval.md").read_text(), changed, repo

    def test_wikilink_forms_become_markdown_links(self):
        text, changed, _ = self.normalised(
            "A [[Association fact]], [[Association fact|the fact]], [[Fact]], [[Association fact#Examples]], "
            "[[Fattura elettronica è]] and [[Billing#Pitfalls|pitfalls]].\n")
        self.assertIn("functional/features/Approval.md", changed)
        self.assertEqual(text, HEAD + "# Approval\n\n"
                         "A [Association fact](../concepts/Association%20fact.md), "
                         "[the fact](../concepts/Association%20fact.md), [Fact](../concepts/Association%20fact.md), "
                         "[Association fact](../concepts/Association%20fact.md#examples), "
                         "[Fattura elettronica è](../concepts/Fattura%20elettronica%20%C3%A8.md) and "
                         "[pitfalls](../../technical/modules/Billing.md#pitfalls).\n")

    def test_link_from_a_deeper_folder(self):
        repo = make_brain(self.tmp.name, {**files_of(page("module", "Billing", "paths: [a/**]")),
                                          "functional/features/billing/Approval.md": HEAD + "Built in [[Billing]].\n"})
        links.normalise(Brain(repo / "brain"))
        self.assertIn("[Billing](../../../technical/modules/Billing.md)",
                      (repo / "brain/functional/features/billing/Approval.md").read_text())

    def test_unknown_title_is_left_and_reported(self):
        text, _, repo = self.normalised("See [[Ghost]].\n")
        self.assertIn("See [[Ghost]].", text)
        code, data, _ = run_cli("validate", cwd=repo)
        self.assertEqual(code, 1)
        self.assertEqual([(e["code"], e["message"]) for e in data["errors"]],
                         [("broken-link", "[[Ghost]] in body matches no page")])

    def test_stale_markdown_path_is_repaired(self):
        text, _, _ = self.normalised("See [the fact](../roles/Association%20fact.md#Examples), [Billing](Billing.md), "
                                     "[docs](https://example.com/x.md) and [gone](Gone.md).\n")
        self.assertIn("[the fact](../concepts/Association%20fact.md#Examples)", text)
        self.assertIn("[Billing](../../technical/modules/Billing.md)", text)
        self.assertIn("[docs](https://example.com/x.md)", text)
        self.assertIn("[gone](Gone.md)", text)

    def test_second_run_changes_nothing(self):
        _, first, repo = self.normalised("[[Fact]] and [[Billing]].\n")
        self.assertEqual(first, sorted(first))
        self.assertEqual(links.normalise(Brain(repo / "brain")), [])

    def test_frontmatter_and_code_untouched(self):
        repo = make_brain(self.tmp.name, files_of(page("module", "Billing", "paths: [a/**]")))
        raw = ("---\ntype: feature\ntitle: \"Approval\"\nsummary: \"Uses [[Billing]]\"  # a comment\nmodules: [Billing]\n"
               "---\n# Approval\n\n```\n[[Billing]]\n```\n\nInline `[[Billing]]` and [[Billing]].\n")
        path = repo / "brain/functional/features/Approval.md"
        path.parent.mkdir(parents=True)
        path.write_text(raw)
        links.normalise(Brain(repo / "brain"))
        self.assertEqual(path.read_text(), raw.replace("and [[Billing]].",
                                                       "and [Billing](../../technical/modules/Billing.md)."))

    def test_heading_inserted_once(self):
        text, _, repo = self.normalised("## Purpose\nApprove.\n")
        self.assertEqual(text, HEAD + "# Approval\n\n## Purpose\nApprove.\n")
        links.normalise(Brain(repo / "brain"))
        self.assertEqual((repo / "brain/functional/features/Approval.md").read_text().count("# Approval"), 1)
        other = (repo / "brain/technical/modules/Billing.md").read_text()
        self.assertTrue(other.endswith("---\n# Billing\n\n## Pitfalls\nx\n"), other)

    def test_heading_does_not_count_towards_the_budget(self):
        _, _, repo = self.normalised("one two three\n")
        self.assertEqual(Brain(repo / "brain").page_at("functional/features/Approval.md").words, 3)

    def test_links_command(self):
        repo, _ = self.brain("[[Billing]]\n")
        code, data, err = run_cli("links", "brain/functional/features/Approval.md", cwd=repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(data, {"changed": ["functional/features/Approval.md"]})
        self.assertIn("[Billing](", (repo / "brain/functional/features/Approval.md").read_text())
        self.assertIn("## Pitfalls", (repo / "brain/technical/modules/Billing.md").read_text())
        self.assertNotIn("# Billing", (repo / "brain/technical/modules/Billing.md").read_text())
        code, data, _ = run_cli("links", cwd=repo)
        self.assertEqual(len(data["changed"]), 3)
        self.assertEqual(run_cli("links", cwd=repo)[1], {"changed": []})


class ReadingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_markdown_links_count_as_links(self):
        repo = make_brain(self.tmp.name, files_of(
            page("module", "Billing", "paths: [a/**]"),
            page("feature", "Approval", "", "In [the module](../../technical/modules/Billing.md#x), "
                                            "[ghost](Ghost.md), [index](../../README.md) and [web](https://x.y/a.md).\n"),
        ))
        brain = Brain(repo / "brain")
        refs = links.refs(brain, "functional/features/Approval.md", brain.page_at("functional/features/Approval.md").body)
        self.assertEqual([(r.name, r.page.title if r.page else None, r.how) for r in refs],
                         [("Billing", "Billing", "path"), ("Ghost", None, None)])
        code, data, _ = run_cli("validate", cwd=repo)
        self.assertEqual([(e["code"], e["target"]) for e in data["errors"]], [("broken-link", "Ghost")])
        run_cli("generate", cwd=repo)
        import json
        self.assertEqual(json.loads((repo / "brain/.pb/backlinks.json").read_text()), {"Billing": ["Approval"]})


class LinkFieldTest(unittest.TestCase):
    def validate(self, *pages):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp, files_of(*pages))
            return run_cli("validate", cwd=repo)[1]

    def test_plain_titles_are_accepted(self):
        data = self.validate(page("role", "Approver"), page("role", "Accountant"),
                             page("feature", "Approval", "roles: [Approver, Accountant]"),
                             page("contract", "Billing API", "provided_by: Billing"),
                             page("module", "Billing", "paths: [a/**]"))
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["warnings"], [])

    def test_wikilink_in_a_link_field_is_rejected(self):
        data = self.validate(page("module", "Billing", "paths: [a/**]"),
                             page("contract", "Billing API", 'provided_by: "[[Billing]]"'),
                             page("feature", "Approval", 'modules: ["[[Billing]]"]'))
        self.assertEqual(sorted((e["path"], e["code"]) for e in data["errors"]),
                         [("functional/features/Approval.md", "bad-kind"), ("technical/contracts/Billing API.md", "bad-kind")])
        self.assertTrue(all("write the page title" in e["message"] for e in data["errors"]))

    def test_link_type_and_broken_link_on_fields(self):
        data = self.validate(page("concept", "Invoice", "term_en: Invoice"),
                             page("feature", "Approval", "modules: [Invoice, Ghost]"))
        self.assertEqual([(e["code"], e["message"]) for e in data["errors"]],
                         [("broken-link", "'Ghost' in field 'modules' matches no page")])
        self.assertIn(("link-type", "field 'modules' expects a module, 'Invoice' is a concept"),
                      [(w["code"], w["message"]) for w in data["warnings"]])


class ReadmeTest(unittest.TestCase):
    def test_readme_is_never_a_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_brain(tmp, {**files_of(page("feature", "Approval"), page("concept", "Readme", "term_en: x")),
                                    "functional/features/README.md": "---\ntype: feature\ntitle: README\n---\nx\n"})
            brain = Brain(repo / "brain")
            self.assertEqual(sorted(p.title for p in brain.pages()), ["Approval", "Readme"])
            data = run_cli("validate", cwd=repo)[1]
            self.assertEqual(sorted((e["path"], e["code"]) for e in data["errors"]),
                             [("functional/concepts/Readme.md", "reserved-title"),
                              ("functional/features/README.md", "reserved-title")])


if __name__ == "__main__":
    unittest.main()


class FixesTest(unittest.TestCase):
    """Review findings I4, M1, M3, M8."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def brain(self, body, extra=()):
        repo = make_brain(self.tmp.name, files_of(
            page("feature", "Approval", "", body),
            page("module", "Billing", "paths: [a/**]", "# Billing\n\n## Expected behaviour\nx\n\n## Pitfalls\ny\n"),
            page("concept", "Association fact", "term_en: Association fact"),
            *extra,
        ))
        return repo

    def text(self, repo):
        return (repo / "brain/functional/features/Approval.md").read_text()

    def test_anchor_becomes_the_github_heading_id(self):
        repo = self.brain("See [[Billing#Expected behaviour|rules]] and [[Billing#Pitfalls]].\n")
        links.normalise(Brain(repo / "brain"))
        self.assertIn("[rules](../../technical/modules/Billing.md#expected-behaviour)", self.text(repo))
        self.assertIn("[Billing](../../technical/modules/Billing.md#pitfalls)", self.text(repo))
        self.assertEqual(run_cli("validate", cwd=repo)[1]["warnings"], [])

    def test_anchor_matching_no_heading(self):
        repo = self.brain("See [[Billing#Nowhere]] and [x](../../technical/modules/Billing.md#gone).\n")
        data = run_cli("validate", cwd=repo)[1]
        self.assertEqual(sorted(w["code"] for w in data["warnings"]), ["broken-anchor", "broken-anchor"])
        links.normalise(Brain(repo / "brain"))
        self.assertIn("See [Billing](../../technical/modules/Billing.md) and", self.text(repo))

    def test_brackets_in_a_label(self):
        repo = self.brain("Many [[Association fact|facts [draft]]] here.\n")
        links.normalise(Brain(repo / "brain"))
        self.assertIn("Many [facts \\[draft\\]](../concepts/Association%20fact.md) here.", self.text(repo))

    def test_comments_and_indented_code_are_left_alone(self):
        body = ("Text.\n\n<!-- [[Billing]] -->\n<!--\n[[Billing]]\n-->\n\n    [[Billing]]\n\n"
                "- item\n\n    [[Billing]] in the list\n")
        repo = self.brain(body)
        links.normalise(Brain(repo / "brain"))
        text = self.text(repo)
        self.assertIn("<!-- [[Billing]] -->\n<!--\n[[Billing]]\n-->\n\n    [[Billing]]\n", text)
        self.assertIn("    [Billing](../../technical/modules/Billing.md) in the list", text)

    def test_unencoded_space_is_encoded(self):
        repo = self.brain("A [x](../concepts/Association fact.md) and [y](../concepts/Association fact.md \"t\").\n")
        links.normalise(Brain(repo / "brain"))
        self.assertIn('A [x](../concepts/Association%20fact.md) and [y](../concepts/Association%20fact.md "t").',
                      self.text(repo))

    def test_reference_definition_rebased_from_a_deeper_page(self):
        repo = make_brain(self.tmp.name, {**files_of(page("module", "Billing", "paths: [a/**]")),
                                          "functional/features/billing/Approval.md":
                                              "---\ntype: feature\ntitle: Approval\n---\nIn [m][b].\n\n"
                                              "[b]: ../../../technical/modules/Billing.md\n"})
        run_cli("generate", cwd=repo)
        self.assertIn("[b]: ../../technical/modules/Billing.md", (repo / "brain/.pb/context/Approval.md").read_text())

    def test_stale_heading_is_replaced(self):
        repo = self.brain("# Old approval\n\nBody.\n")
        links.normalise(Brain(repo / "brain"))
        self.assertTrue(self.text(repo).endswith("---\n# Approval\n\nBody.\n"))

    def test_links_check_changes_nothing(self):
        repo = self.brain("[[Billing]]\n")
        before = self.text(repo)
        code, data, _ = run_cli("links", "--check", cwd=repo)
        self.assertEqual(code, 1)
        self.assertIn("functional/features/Approval.md", data["changed"])
        self.assertEqual(self.text(repo), before)
        run_cli("links", cwd=repo)
        self.assertEqual(run_cli("links", "--check", cwd=repo)[:2], (0, {"changed": []}))
