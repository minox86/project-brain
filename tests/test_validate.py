import tempfile
import unittest

from helpers import make_brain, page, files_of, run_cli


def codes(data, key="errors"):
    return sorted({f["code"] for f in data[key]})


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_on(self, files, *paths):
        repo = make_brain(self.tmp.name, files)
        return run_cli("validate", *paths, cwd=repo)

    def assertError(self, files, code):
        exit_code, data, _ = self.run_on(files)
        self.assertEqual(exit_code, 1, data)
        self.assertIn(code, codes(data), data)

    def test_clean(self):
        code, data, _ = self.run_on(files_of(
            page("module", "Billing", "paths: [services/billing/**]"),
            page("contract", "Billing API", 'kind: api\nprovided_by: Billing'),
            page("decision", "Use REST", 'area: technical\ndate: 2026-10-31\naffects: [Billing]', "See [[Billing API#Semantics|the API]].\n"),
        ))
        self.assertEqual(code, 0, data)
        self.assertEqual(data["errors"], [])

    def test_frontmatter(self):
        self.assertError({"decisions/X.md": "---\ntype: decision\ntitle: [x\n---\n"}, "frontmatter")

    def test_missing_type(self):
        self.assertError({"decisions/X.md": "---\ntitle: X\n---\n"}, "missing-type")

    def test_no_frontmatter_is_missing_type(self):
        self.assertError({"decisions/X.md": "just text\n"}, "missing-type")

    def test_unknown_type(self):
        self.assertError({"decisions/X.md": "---\ntype: persona\ntitle: X\n---\n"}, "unknown-type")

    def test_missing_title(self):
        self.assertError({"decisions/X.md": "---\ntype: decision\narea: ux\n---\n"}, "missing-title")

    def test_title_mismatch(self):
        self.assertError({"decisions/X.md": "---\ntype: decision\ntitle: Y\narea: ux\n---\n"}, "title-mismatch")

    def test_bad_title_chars(self):
        self.assertError({"decisions/A#B.md": "---\ntype: decision\ntitle: \"A#B\"\narea: ux\n---\n"}, "bad-title-chars")

    def test_duplicate_title(self):
        self.assertError(files_of(
            page("concept", "Invoice", "term_en: Invoice"),
            page("feature", "invoice"),
        ), "duplicate-title")

    def test_alias_colliding_with_title(self):
        self.assertError(files_of(
            page("concept", "Invoice", "term_en: Invoice\naliases: [Bill]"),
            page("concept", "Bill", "term_en: Bill"),
        ), "duplicate-title")

    def test_wrong_folder(self):
        _, text = page("decision", "X", "area: ux")
        self.assertError({"open-questions/X.md": text}, "wrong-folder")

    def test_a_decision_lives_in_the_folder_of_its_area(self):
        code, data, _ = self.run_on(files_of(
            page("decision", "Scope", "area: cross"),
            page("decision", "Use REST", "area: technical"),
            page("decision", "Single approver", "area: functional"),
            page("decision", "One click", "area: ux"),
        ))
        self.assertEqual((code, data["errors"]), (0, []), data)
        for area, home in (("technical", "technical/decisions"), ("functional", "functional/decisions"),
                           ("ux", "functional/decisions"), ("cross", "decisions")):
            _, text = page("decision", "X", f"area: {area}")
            wrong = "decisions" if home != "decisions" else "technical/decisions"
            repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name), {f"{wrong}/X.md": text})
            _, data, _ = run_cli("validate", cwd=repo)
            found = [e for e in data["errors"] if e["code"] == "wrong-folder"]
            self.assertEqual(len(found), 1, data)
            self.assertIn(f"area '{area}' lives in {home}/", found[0]["message"])

    def test_a_type_without_area_folders_keeps_one_folder(self):
        # A brain created before area_folders existed: its decisions stay in decisions/, whatever their area.
        repo = make_brain(self.tmp.name, {"decisions/X.md": page("decision", "X", "area: technical")[1]})
        schema = repo / "brain/.pb/schema/types/decision.md"
        schema.write_text("".join(l for l in schema.read_text().splitlines(True) if not l.startswith("area_folders")))
        code, data, _ = run_cli("validate", cwd=repo)
        self.assertEqual((code, data["errors"]), (0, []), data)
        run_cli("generate", cwd=repo)
        self.assertIn("[X](X.md)", (repo / "brain/decisions/README.md").read_text())
        self.assertFalse((repo / "brain/technical/decisions").exists())

    def test_bad_area_folders(self):
        def messages(line):
            repo = make_brain(tempfile.mkdtemp(dir=self.tmp.name))
            schema = repo / "brain/.pb/schema/types/decision.md"
            lines = schema.read_text().splitlines(True)
            schema.write_text("".join(line + "\n" if l.startswith("area_folders") else l for l in lines))
            _, data, _ = run_cli("validate", cwd=repo)
            return [e["message"] for e in data["errors"] if e["code"] == "bad-area-folders"]
        self.assertIn("not a value of the `area` field", messages("area_folders: {legal: legal/decisions}")[0])
        self.assertIn("is a folder of type 'module'", messages("area_folders: {technical: technical/modules}")[0])
        self.assertIn("must map values", messages("area_folders: [technical]")[0])

    def test_missing_required(self):
        self.assertError(files_of(page("module", "Billing")), "missing-required")

    def test_bad_enum(self):
        self.assertError(files_of(page("decision", "X", "area: legal")), "bad-enum")

    def test_bad_date(self):
        self.assertError(files_of(page("decision", "X", "area: ux\ndate: 31/10/2026")), "bad-date")

    def test_bad_kind(self):
        self.assertError(files_of(page("module", "Billing", "paths: services/billing")), "bad-kind")

    def test_broken_link_in_body_and_field(self):
        exit_code, data, _ = self.run_on(files_of(
            page("decision", "X", 'area: ux\naffects: [Ghost]', "See [[Phantom]].\n"),
        ))
        self.assertEqual(exit_code, 1)
        broken = [f for f in data["errors"] if f["code"] == "broken-link"]
        self.assertEqual(len(broken), 2)

    def test_secret(self):
        self.assertError(files_of(page("environment", "Prod", "kind: prod", "password: Sup3rS3cretValue\n")), "secret")

    def test_secret_in_raw_and_digest(self):
        self.assertError({".pb/raw/2026/10/x.md": "---\nkind: file\n---\nAKIAABCDEFGHIJKLMNOP\n"}, "secret")
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.assertError({".pb/digests/2026-10-31.md": "ghp_" + "b" * 36 + "\n"}, "secret")

    def test_alias_link_is_warning(self):
        code, data, _ = self.run_on(files_of(
            page("concept", "Invoice", "term_en: Invoice\naliases: [Bill]"),
            page("decision", "X", 'area: functional\naffects: [Bill]'),
        ))
        self.assertEqual(code, 0, data)
        self.assertIn("alias-link", codes(data, "warnings"))

    def test_unknown_field_and_link_type_warnings(self):
        code, data, _ = self.run_on(files_of(
            page("concept", "Invoice", "term_en: Invoice\ncolour: red"),
            page("feature", "Approval", 'modules: [Invoice]'),
        ))
        self.assertEqual(code, 0, data)
        self.assertEqual(codes(data, "warnings"), ["link-type", "unknown-field"])

    def test_over_budget_warning_not_error(self):
        code, data, _ = self.run_on(files_of(page("concept", "Invoice", "term_en: Invoice", "word " * 251)))
        self.assertEqual(code, 0)
        warning = [w for w in data["warnings"] if w["code"] == "over-budget"][0]
        self.assertIn("251", warning["message"])
        self.assertIn("250", warning["message"])

    def test_raw_too_long_warning(self):
        code, data, _ = self.run_on({".pb/raw/2026/10/x.md": "---\nkind: file\n---\n" + "w " * 3001})
        self.assertEqual(code, 0)
        self.assertIn("raw-too-long", codes(data, "warnings"))

    def test_paths_argument_limits_scope_but_duplicates_checked_globally(self):
        files = files_of(
            page("concept", "Invoice", "term_en: Invoice"),
            page("feature", "invoice"),
            page("decision", "Other", "area: legal"),
        )
        code, data, _ = self.run_on(files, "brain/functional/features/invoice.md")
        self.assertEqual(code, 1)
        self.assertEqual(codes(data), ["duplicate-title"])
        self.assertTrue(all(f["path"] == "functional/features/invoice.md" for f in data["errors"]))

    def test_malformed_page_does_not_crash(self):
        code, data, _ = self.run_on({
            **files_of(page("module", "Billing", "paths: [a/**]")),
            "technical/modules/Bad.md": "---\ntype: module\n",
        })
        self.assertEqual(code, 1)
        self.assertEqual(codes(data), ["frontmatter"])


if __name__ == "__main__":
    unittest.main()
