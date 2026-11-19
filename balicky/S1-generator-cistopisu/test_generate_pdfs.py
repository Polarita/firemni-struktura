# -*- coding: utf-8 -*-
"""
Tests of the PDF generator of package S1 (Version 2.8).
Testy generátoru PDF balíčku S1 (Verze 2.8).

Usage / Použití:  python -m unittest -v test_generate_pdfs
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

import generate_pdfs as gen


class FillTests(unittest.TestCase):
    def test_fill_replaces_all_variables(self) -> None:
        self.assertEqual(gen.fill("# A\n{{spis_id}} / {{ ico_klienta }}", {"spis_id": "POL-2027-00001", "ico_klienta": "00000000"}, "t"),
                         "# A\nPOL-2027-00001 / 00000000")

    def test_missing_unused_empty_and_malformed_values_fail(self) -> None:
        with self.assertRaises(gen.GeneratorError):
            gen.fill("{{spis_id}}", {}, "t")
        with self.assertRaises(gen.GeneratorError):
            gen.fill("{{spis_id}}", {"spis_id": "x", "navic": "y"}, "t")
        with self.assertRaises(gen.GeneratorError):
            gen.fill("{{spis_id}}", {"spis_id": " "}, "t")
        with self.assertRaises(gen.GeneratorError):
            gen.fill("{{Spis ID}}", {}, "t")
        with self.assertRaises(gen.GeneratorError):
            gen.fill("{{spis_id", {"spis_id": "x"}, "t")
        with self.assertRaises(gen.GeneratorError):
            gen.fill("{{spis_id}}", ["not", "a", "dict"], "t")  # type: ignore[arg-type]


class RepositoryTemplatesTests(unittest.TestCase):
    def test_all_eight_sets_have_templates_and_matching_sample_data(self) -> None:
        results = gen.generate(gen.TEMPLATE_DIR, gen.DATA_DIR, Path(tempfile.gettempdir()), None, True, True)
        self.assertGreaterEqual(len(results), 8)
        self.assertEqual({r["template"][:2] for r in results}, set(gen.REQUIRED_SETS))

    def test_templates_contain_no_html_and_no_personal_identifiers(self) -> None:
        for path in sorted(gen.TEMPLATE_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"<(div|span|table|br|img|script)\b", path.name)
            self.assertNotIn("{{rodne_cislo}}", text, path.name)
            self.assertTrue(text.splitlines()[1 if text.splitlines()[1].strip() else 2].startswith("**Spis:**"), path.name)

    def test_data_values_cannot_inject_html_markdown_or_break_tables(self) -> None:
        # EN: Values come from people and systems; they must never become HTML or Markdown markup.
        # CZ: Hodnoty pocházejí od lidí a systémů; nikdy se nesmějí stát HTML ani Markdown značkami.
        template = "| Položka | Hodnota |\n| :--- | :--- |\n| Název | {{nazev}} |\n"
        payload = "<script>alert(1)</script> ![x](file:///etc/passwd) [l](https://bad.test) | a & b\n| další"
        filled = gen.fill(template, {"nazev": payload}, "test")
        self.assertNotIn("<script>", filled)
        self.assertIn("&lt;script&gt;", filled)
        self.assertEqual(filled.count("\n"), template.count("\n"))
        self.assertEqual([line.count("|") for line in filled.splitlines()], [line.count("|") for line in template.splitlines()])
        rendered_html = gen.to_html(filled, "test", False, "footer")
        self.assertNotIn("<img", rendered_html)
        self.assertNotIn("<a ", rendered_html)
        self.assertNotIn("<script", rendered_html)

    def test_sample_data_are_flat_string_objects(self) -> None:
        for path in sorted(gen.DATA_DIR.glob("*.json")):
            values = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(values, dict, path.name)
            self.assertTrue(all(isinstance(v, str) and v.strip() for v in values.values()), path.name)


class PdfTests(unittest.TestCase):
    def test_single_document_prints_a_valid_pdf_with_manifest(self) -> None:
        try:
            gen.find_browser()
        except gen.GeneratorError:
            self.skipTest("no Chromium browser available / není dostupný prohlížeč Chromium")
        with tempfile.TemporaryDirectory() as tmp:
            results = gen.generate(gen.TEMPLATE_DIR, gen.DATA_DIR, Path(tmp), "07-predzalobni-vyzva", True, False)
            self.assertEqual(len(results), 1)
            pdf = Path(tmp) / "07-predzalobni-vyzva.pdf"
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            manifest = json.loads((Path(tmp) / "07-predzalobni-vyzva.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"]["pdf"], gen.sha256(pdf))
            self.assertGreaterEqual(manifest["pages"], 1)

    def test_final_mode_omits_watermark_and_internal_ai_footer(self) -> None:
        try:
            gen.find_browser()
        except gen.GeneratorError:
            self.skipTest("no Chromium browser available / není dostupný prohlížeč Chromium")
        with tempfile.TemporaryDirectory() as tmp:
            gen.generate(gen.TEMPLATE_DIR, gen.DATA_DIR, Path(tmp), "07-predzalobni-vyzva", False, False)
            pdf = Path(tmp) / "07-predzalobni-vyzva.pdf"
            text = "".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)
            self.assertNotIn("VZOR s fiktivními daty", text)
            self.assertNotIn("koncept ai", text)
            self.assertNotIn("15001", text)
            self.assertNotIn("1001", text)
            self.assertIn("SPD*1.0*", text)
            self.assertNotIn("&#42;", text)
            html_final = gen.to_html("# Doc\nText", "Doc", False, "Polarita s.r.o.")
            self.assertNotIn('<div class="watermark">', html_final)


if __name__ == "__main__":
    unittest.main()
