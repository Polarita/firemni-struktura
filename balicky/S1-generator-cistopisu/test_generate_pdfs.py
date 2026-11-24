# -*- coding: utf-8 -*-
"""
Tests of the PDF generator of package S1 (Version 3.15).
Testy generátoru PDF balíčku S1 (Verze 3.15).

Usage / Použití:  python -m unittest -v test_generate_pdfs

EN: The two print tests need a Chromium browser. Without one they are skipped - unless the variable
    POLARITA_REQUIRE_BROWSER=1 is set (CI), then a missing browser is a failure.
CZ: Dva tiskové testy potřebují prohlížeč Chromium. Bez něj se přeskočí - pokud není nastavena
    proměnná POLARITA_REQUIRE_BROWSER=1 (CI), pak je chybějící prohlížeč selháním.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def _minimal_pdf(text: str) -> bytes:
    """Hand-made one-page PDF with the given ASCII text. / Ručně složené jednostránkové PDF s daným ASCII textem."""
    stream = ("BT /F1 8 Tf 20 800 Td (" + text + ") Tj ET").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 3000 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = b"%PDF-1.4\n"
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return out + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref


def _fake_browser(folder: Path, mode: str) -> str:
    """
    EN: Stand-in for the browser (a Python script): "noop" exits 0 without writing, "fail" exits 1,
        "old" writes a PDF of another case, "good" writes a PDF that names the case number of the sample data.
    CZ: Maketa prohlížeče (skript v Pythonu): "noop" skončí 0 a nic nezapíše, "fail" skončí 1, "old"
        zapíše PDF jiného spisu, "good" zapíše PDF s číslem spisu ze vzorových dat.
    """
    pdf = folder / f"{mode}.pdf"
    pdf.write_bytes(_minimal_pdf(("Dokument ke spisu POL-2027-00001 . " if mode == "good" else "Stary dokument POL-1999-99999 . ") * 8))
    script = folder / f"browser_{mode}.py"
    script.write_text(
        "import shutil, sys\n"
        f"mode, source = {mode!r}, {str(pdf)!r}\n"
        "target = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--print-to-pdf='))\n"
        "if mode in ('good', 'old'):\n    shutil.copyfile(source, target)\n"
        "sys.exit(1 if mode == 'fail' else 0)\n", encoding="utf-8")
    if os.name == "nt":
        launcher = folder / f"browser_{mode}.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / f"browser_{mode}.sh"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    return str(launcher)


class PrintPathTests(unittest.TestCase):
    """The print path with a stand-in browser - runs everywhere. / Tisková cesta s maketou prohlížeče - běží všude."""

    NAME = "07-predzalobni-vyzva"

    def run_with(self, mode: str, out: Path) -> list:
        with tempfile.TemporaryDirectory() as tools:
            with mock.patch.object(gen, "BROWSER_CANDIDATES", (_fake_browser(Path(tools), mode),)):
                return gen.generate(gen.TEMPLATE_DIR, gen.DATA_DIR, out, self.NAME, True, False)

    def test_good_print_writes_pdf_and_manifest_with_matching_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(len(self.run_with("good", Path(tmp))), 1)
            manifest = json.loads((Path(tmp) / f"{self.NAME}.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"]["pdf"], gen.sha256(Path(tmp) / f"{self.NAME}.pdf"))
            self.assertEqual(manifest["sha256"]["template"], gen.sha256(gen.TEMPLATE_DIR / f"{self.NAME}.md"))
            self.assertEqual(manifest["sha256"]["data"], gen.sha256(gen.DATA_DIR / f"{self.NAME}.json"))
            self.assertEqual(manifest["variables"], json.loads((gen.DATA_DIR / f"{self.NAME}.json").read_text(encoding="utf-8")))

    def test_invalid_inputs_withdraw_the_older_pdf_and_manifest(self) -> None:
        # EN: After a bad edit of the data or the template the older clean copy must not stay as a valid pair.
        # CZ: Po chybné úpravě dat nebo šablony nesmí starší čistopis zůstat jako platná dvojice.
        good_data = (gen.DATA_DIR / f"{self.NAME}.json").read_text(encoding="utf-8")
        good_template = (gen.TEMPLATE_DIR / f"{self.NAME}.md").read_text(encoding="utf-8")
        values = json.loads(good_data)
        missing = dict(list(values.items())[1:])
        defects = {
            "broken json": (good_template, "{"),
            "missing variable": (good_template, json.dumps(missing, ensure_ascii=False)),
            "no heading": (good_template.lstrip("# "), good_data),
            "no data file": (good_template, None),
        }
        for label, (template, data) in defects.items():
            with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tools:
                out, templates, datas = Path(tmp) / "out", Path(tmp) / "sablony", Path(tmp) / "data"
                templates.mkdir(), datas.mkdir()
                (templates / f"{self.NAME}.md").write_text(good_template, encoding="utf-8")
                (datas / f"{self.NAME}.json").write_text(good_data, encoding="utf-8")
                with mock.patch.object(gen, "BROWSER_CANDIDATES", (_fake_browser(Path(tools), "good"),)):
                    gen.generate(templates, datas, out, self.NAME, True, False)
                    self.assertEqual(len(list(out.iterdir())), 2, label)
                    (templates / f"{self.NAME}.md").write_text(template, encoding="utf-8")
                    if data is None:
                        (datas / f"{self.NAME}.json").unlink()
                    else:
                        (datas / f"{self.NAME}.json").write_text(data, encoding="utf-8")
                    # EN: --check reports the defect but never touches the outputs. / CZ: --check vadu ohlásí, ale na výstupy nesahá.
                    with self.assertRaises(gen.GeneratorError, msg=label):
                        gen.generate(templates, datas, out, self.NAME, True, True)
                    self.assertEqual(len(list(out.iterdir())), 2, label)
                    with self.assertRaises(gen.GeneratorError, msg=label):
                        gen.generate(templates, datas, out, self.NAME, True, False)
                self.assertEqual(sorted(p.name for p in out.iterdir()), [], label)

    def test_invalid_input_never_deletes_the_output_protected_by_a_held_lock(self) -> None:
        # EN: While another run holds the lock of the document, a run with a defective input fails on the
        #     lock (existing semantics: refusal, no waiting) and removes nothing; once the lock is free,
        #     the same defect withdraws the pair.
        # CZ: Dokud zámek dokumentu drží jiný běh, běh s vadným vstupem selže na zámku (stávající
        #     semantika: odmítnutí, žádné čekání) a nic neodstraní; po uvolnění zámku táž vada dvojici stáhne.
        good_data = (gen.DATA_DIR / f"{self.NAME}.json").read_text(encoding="utf-8")
        good_template = (gen.TEMPLATE_DIR / f"{self.NAME}.md").read_text(encoding="utf-8")
        for label, (template, data) in {"broken json": (good_template, "{"), "no heading": (good_template.lstrip("# "), good_data),
                                        "no data file": (good_template, None), "no template": (None, good_data)}.items():
            with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tools:
                out, templates, datas = Path(tmp) / "out", Path(tmp) / "sablony", Path(tmp) / "data"
                templates.mkdir(), datas.mkdir()
                (templates / f"{self.NAME}.md").write_text(good_template, encoding="utf-8")
                (datas / f"{self.NAME}.json").write_text(good_data, encoding="utf-8")
                with mock.patch.object(gen, "BROWSER_CANDIDATES", (_fake_browser(Path(tools), "good"),)):
                    gen.generate(templates, datas, out, self.NAME, True, False)
                    before = {p.name: p.read_bytes() for p in out.iterdir()}
                    self.assertEqual(len(before), 2, label)
                    for folder, suffix, content in ((templates, "md", template), (datas, "json", data)):
                        if content is None:
                            (folder / f"{self.NAME}.{suffix}").unlink()
                        else:
                            (folder / f"{self.NAME}.{suffix}").write_text(content, encoding="utf-8")
                    with gen._DocumentLock(out, self.NAME):
                        with self.assertRaises(gen.GeneratorError, msg=label) as caught:
                            gen.generate(templates, datas, out, self.NAME, True, False)
                        self.assertIn("another generation", str(caught.exception), label)
                        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir() if not p.name.endswith(".lock")}, before, label)
                    with self.assertRaises(gen.GeneratorError, msg=label) as caught:
                        gen.generate(templates, datas, out, self.NAME, True, False)
                    self.assertNotIn("another generation", str(caught.exception), label)
                self.assertEqual(sorted(p.name for p in out.iterdir()), [], label)

    def test_missing_template_withdraws_the_older_pdf_and_manifest(self) -> None:
        # EN: A removed template is an invalid input too: --only withdraws the named pair, a full run every
        #     pair whose manifest has no template. --check and foreign files are left alone.
        # CZ: Odstraněná šablona je také vadný vstup: --only stáhne jmenovanou dvojici, plný běh každou
        #     dvojici, jejíž manifest nemá šablonu. --check ani cizí soubory se nedotknou.
        good_data = (gen.DATA_DIR / f"{self.NAME}.json").read_text(encoding="utf-8")
        good_template = (gen.TEMPLATE_DIR / f"{self.NAME}.md").read_text(encoding="utf-8")
        for only in (self.NAME, None):
            with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tools:
                out, templates, datas = Path(tmp) / "out", Path(tmp) / "sablony", Path(tmp) / "data"
                templates.mkdir(), datas.mkdir()
                (templates / f"{self.NAME}.md").write_text(good_template, encoding="utf-8")
                (datas / f"{self.NAME}.json").write_text(good_data, encoding="utf-8")
                with mock.patch.object(gen, "BROWSER_CANDIDATES", (_fake_browser(Path(tools), "good"),)):
                    gen.generate(templates, datas, out, self.NAME, True, False)
                    (out / "cizi.pdf").write_bytes(b"%PDF-foreign")
                    self.assertEqual(len(list(out.iterdir())), 3, only)
                    (templates / f"{self.NAME}.md").unlink()
                    with self.assertRaises(gen.GeneratorError, msg=only):
                        gen.generate(templates, datas, out, only, True, True)
                    self.assertEqual(len(list(out.iterdir())), 3, only)
                    with self.assertRaises(gen.GeneratorError, msg=only):
                        gen.generate(templates, datas, out, only, True, False)
                self.assertEqual(sorted(p.name for p in out.iterdir()), ["cizi.pdf"], only)
        # EN: A name that is not a plain file stem never reaches outside the output folder.
        # CZ: Název, který není prostým názvem souboru, nikdy nesáhne mimo výstupní složku.
        with tempfile.TemporaryDirectory() as tmp:
            out, templates = Path(tmp) / "out", Path(tmp) / "sablony"
            out.mkdir(), templates.mkdir()
            (Path(tmp) / "x.manifest.json").write_text("{}", encoding="utf-8")
            (Path(tmp) / "x.pdf").write_bytes(b"%PDF-outside")
            self.assertEqual(gen.withdraw_without_template(templates, out, "../x"), [])
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["out", "sablony", "x.manifest.json", "x.pdf"])

    def test_interrupted_publication_never_leaves_a_manifest_of_another_pdf(self) -> None:
        # EN: The publication fails at each of its steps; whatever manifest exists afterwards describes the PDF next to it.
        # CZ: Zveřejnění selže v každém svém kroku; jakýkoli manifest, který potom existuje, popisuje PDF vedle sebe.
        real_replace = os.replace
        for failing_step in (1, 2):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                self.run_with("good", out)   # an older complete pair / starší úplná dvojice
                old_pdf = (out / f"{self.NAME}.pdf").read_bytes()
                calls = []

                def flaky(source, target, failing_step=failing_step, calls=calls):
                    calls.append(target)
                    if len(calls) == failing_step:
                        raise OSError("disk full")
                    return real_replace(source, target)

                with mock.patch.object(gen.os, "replace", flaky), self.assertRaises(gen.GeneratorError):
                    self.run_with("good", out)
                self.assertFalse((out / f"{self.NAME}.manifest.json").exists(), failing_step)
                self.assertEqual(sorted(p.name for p in out.iterdir()), [f"{self.NAME}.pdf"], failing_step)
                if failing_step == 1:
                    self.assertEqual((out / f"{self.NAME}.pdf").read_bytes(), old_pdf)
                # EN: The next run repairs the pair; no lock or staging folder is left behind.
                # CZ: Další běh dvojici opraví; nezůstane žádný zámek ani přípravná složka.
                self.run_with("good", out)
                manifest = json.loads((out / f"{self.NAME}.manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["sha256"]["pdf"], gen.sha256(out / f"{self.NAME}.pdf"))
                self.assertEqual(sorted(p.name for p in out.iterdir()), [f"{self.NAME}.manifest.json", f"{self.NAME}.pdf"])

    def test_publish_takes_the_hash_from_the_staged_pdf_and_orders_the_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            staging = out / ".x.staging-1"
            staging.mkdir()
            staged = staging / "x.pdf"
            staged.write_bytes(b"%PDF-new")
            (out / "x.pdf").write_bytes(b"%PDF-old")
            (out / "x.manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(gen.GeneratorError):   # a manifest of another PDF is refused / manifest jiného PDF se odmítne
                gen.publish(out, "x", staged, {"sha256": {"pdf": gen.sha256(out / "x.pdf")}})
            self.assertEqual((out / "x.pdf").read_bytes(), b"%PDF-old")
            order = []
            real_replace, real_unlink = os.replace, Path.unlink

            def traced_unlink(path, *args, **kwargs):
                order.append(("unlink", Path(path).name))
                return real_unlink(path, *args, **kwargs)

            def traced_replace(source, target):
                order.append(("replace", Path(target).name))
                return real_replace(source, target)

            with mock.patch.object(gen.os, "replace", traced_replace), mock.patch.object(Path, "unlink", traced_unlink):
                gen.publish(out, "x", staged, {"sha256": {"pdf": gen.sha256(staged)}})
            self.assertEqual(order, [("unlink", "x.manifest.json"), ("replace", "x.pdf"), ("replace", "x.manifest.json")])
            self.assertEqual(json.loads((out / "x.manifest.json").read_text(encoding="utf-8"))["sha256"]["pdf"], gen.sha256(out / "x.pdf"))

    def test_parallel_generation_of_the_same_document_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.run_with("good", out)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            with gen._DocumentLock(out, self.NAME):
                with self.assertRaises(gen.GeneratorError) as caught:
                    self.run_with("good", out)
                self.assertIn("another generation", str(caught.exception))
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir() if not p.name.endswith(".lock")}, before)
            self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(before))
            self.run_with("good", out)

    def test_failed_print_never_accepts_or_keeps_an_older_pdf(self) -> None:
        # EN: A browser that exits 0 without writing, fails, or produces a PDF of another case.
        # CZ: Prohlížeč, který skončí 0 a nic nezapíše, selže, nebo vyrobí PDF jiného spisu.
        for mode in ("noop", "fail", "old"):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                self.run_with("good", out)   # a previous successful run / předchozí úspěšný běh
                with self.assertRaises(gen.GeneratorError, msg=mode):
                    self.run_with(mode, out)
                self.assertEqual(sorted(p.name for p in out.iterdir()), [], mode)

    def test_main_returns_one_when_the_browser_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tools:
            with mock.patch.object(gen, "BROWSER_CANDIDATES", (_fake_browser(Path(tools), "noop"),)), \
                    mock.patch("sys.stderr"):
                self.assertEqual(gen.main(["--only", self.NAME, "--output-dir", tmp]), 1)
            with mock.patch.object(gen, "BROWSER_CANDIDATES", (_fake_browser(Path(tools), "good"),)), \
                    mock.patch("sys.stdout"):
                self.assertEqual(gen.main(["--only", self.NAME, "--output-dir", tmp]), 0)

    def test_printed_page_forbids_scripts_and_remote_loads(self) -> None:
        page = gen.to_html("# Doc\nText", "Doc", True, "footer")
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("default-src 'none'", page)


class TemplateRuleTests(unittest.TestCase):
    def test_raw_html_and_placeholder_in_code_are_refused(self) -> None:
        for bad in ('<IMG src="file:///etc/passwd">', '<iframe src="x"></iframe>', "<object data=x>", "<style>*{display:none}</style>",
                    "<svg onload=alert(1)>", '<a href="http://10.0.0.1/">x</a>', "<link rel=stylesheet href=x>", "<Script>x</Script>",
                    "<!-- komentář -->", "<br>", "<script", "`{{spis_id}}`", "```\n{{spis_id}}\n```"):
            with self.assertRaises(gen.GeneratorError, msg=bad):
                gen.fill("# T\n" + bad + "\n{{spis_id}}\n", {"spis_id": "POL-2027-00001"}, "t")
        self.assertIn("POL-2027-00001", gen.fill("# T\nméně než < 30 min a `kód`\n{{spis_id}}\n", {"spis_id": "POL-2027-00001"}, "t"))

    def test_value_cannot_start_a_markdown_block(self) -> None:
        import markdown
        for value in ("===", "---", "- bod", "+ bod", "1. bod", "12) bod", "= x"):
            for template in ("# T\n\nOdstavec.\n{{x}}\n\nDalší.\n", "# T\n\n{{x}}\n"):
                rendered = markdown.markdown(gen.fill(template, {"x": value}, "t"), extensions=["tables", "sane_lists"])
                self.assertEqual(rendered.count("<h1>"), 1, value)
                for tag in ("<h2", "<ul", "<ol", "<hr", "<li"):
                    self.assertNotIn(tag, rendered, value)
        self.assertEqual(gen.escape_value("86\u00a0450,00\u00a0Kč"), "86\u00a0450,00\u00a0Kč")
        self.assertEqual(gen.escape_value("  a \n b\t c "), "a b c")


class RepositoryTemplatesTests(unittest.TestCase):
    def test_all_eight_sets_have_templates_and_matching_sample_data(self) -> None:
        results = gen.generate(gen.TEMPLATE_DIR, gen.DATA_DIR, Path(tempfile.gettempdir()), None, True, True)
        self.assertGreaterEqual(len(results), 8)
        self.assertEqual({r["template"][:2] for r in results}, set(gen.REQUIRED_SETS))

    def test_templates_contain_no_html_and_no_personal_identifiers(self) -> None:
        for path in sorted(gen.TEMPLATE_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            gen.check_template(text, path.name)   # no raw HTML, no placeholder inside code / žádné surové HTML ani proměnná v kódu
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


def _real_browser_or_skip(test: unittest.TestCase) -> None:
    try:
        gen.find_browser()
    except gen.GeneratorError:
        if os.environ.get(gen.REQUIRE_BROWSER_ENV) == "1":
            test.fail(f"{gen.REQUIRE_BROWSER_ENV}=1 and no Chromium browser found (set POLARITA_PDF_BROWSER)")
        test.skipTest("no Chromium browser available / není dostupný prohlížeč Chromium")


class PdfTests(unittest.TestCase):
    def test_single_document_prints_a_valid_pdf_with_manifest(self) -> None:
        _real_browser_or_skip(self)
        with tempfile.TemporaryDirectory() as tmp:
            results = gen.generate(gen.TEMPLATE_DIR, gen.DATA_DIR, Path(tmp), "07-predzalobni-vyzva", True, False)
            self.assertEqual(len(results), 1)
            pdf = Path(tmp) / "07-predzalobni-vyzva.pdf"
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            manifest = json.loads((Path(tmp) / "07-predzalobni-vyzva.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"]["pdf"], gen.sha256(pdf))
            self.assertGreaterEqual(manifest["pages"], 1)

    def test_final_mode_omits_watermark_and_internal_ai_footer(self) -> None:
        _real_browser_or_skip(self)
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
            self.assertIn("POL-2027-00001", "".join(text.split()))
            html_final = gen.to_html("# Doc\nText", "Doc", False, "Polarita s.r.o.")
            self.assertNotIn('<div class="watermark">', html_final)


if __name__ == "__main__":
    unittest.main()
