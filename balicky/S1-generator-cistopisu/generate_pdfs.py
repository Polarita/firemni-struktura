# -*- coding: utf-8 -*-
"""
Generator of clean PDF copies of contracts and protocols (package S1, Version 2.8).
Generátor PDF čistopisů smluv a protokolů (balíček S1, Verze 2.8).

EN: Fills Markdown templates from sablony/ with variables from data/<same-name>.json,
    renders them to print HTML (A4) and prints PDF through a headless Chromium browser
    (Chrome / Edge). For every document it writes a manifest with the variables and SHA-256
    hashes of template, data and PDF — the input of the transactional diff "mutation_confirm".
    Exit code 0 is returned only when every template of all eight sets produced a valid PDF.
CZ: Vyplní Markdown šablony ze sablony/ proměnnými z data/<stejný-název>.json, vysází je do
    tiskového HTML (A4) a vytiskne PDF přes headless prohlížeč Chromium (Chrome / Edge).
    Ke každému dokumentu zapíše manifest s proměnnými a SHA-256 otisky šablony, dat a PDF —
    vstup transakčního diffu „mutation_confirm“. Návratový kód 0 se vrací pouze tehdy, když
    každá šablona všech osmi sestav vytvořila platné PDF.

Usage / Použití:
    python generate_pdfs.py                      # all templates with sample data, watermark VZOR
    python generate_pdfs.py --check              # validate templates and data only / jen kontrola
    python generate_pdfs.py --only 07-predzalobni-vyzva --data-dir cesta/k/datum --final

Requires / Vyžaduje: Python packages "markdown" and "pypdf" (see requirements.txt) and Chrome or Edge.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE / "sablony"
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "vystup"

PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
ANY_BRACES = re.compile(r"\{\{.*?\}\}", re.DOTALL)
REQUIRED_SETS = ("01", "02", "03", "04", "05", "06", "07", "08")  # eight sets of package S1 / osm sestav balíčku S1
SHARED_VARIABLES = ("spis_id", "ico_klienta", "castka_bez_dph")    # variables named by the S1 definition of done

_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
    "|": "&#124;",
    "\\": "&#92;",
    "`": "&#96;",
    "*": "&#42;",
    "_": "&#95;",
    "[": "&#91;",
    "]": "&#93;",
    "(": "&#40;",
    ")": "&#41;",
    "!": "&#33;",
    "#": "&#35;",
    "~": "&#126;",
}
_ESCAPE_RE = re.compile("|".join(re.escape(k) for k in _ESCAPE_MAP))

BROWSER_CANDIDATES = (
    os.environ.get("POLARITA_PDF_BROWSER", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "chromium", "chromium-browser", "google-chrome", "microsoft-edge",
)

PAGE_CSS = """
@page { size: A4; margin: 22mm 20mm 20mm 20mm; @bottom-center { content: counter(page) " / " counter(pages); font: 8.5pt "Segoe UI", Arial, sans-serif; color: #555; } }
* { box-sizing: border-box; }
body { font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.45; color: #111; margin: 0; }
h1 { font-size: 16pt; text-align: center; margin: 0 0 4mm; line-height: 1.25; }
h2 { font-size: 11.5pt; margin: 6mm 0 2mm; break-after: avoid; }
h3 { font-size: 10.5pt; margin: 4mm 0 1.5mm; break-after: avoid; }
p { margin: 0 0 2.2mm; text-align: justify; hyphens: auto; }
ol, ul { margin: 0 0 2.2mm; padding-left: 7mm; } li { margin: 0 0 1.2mm; text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9.5pt; break-inside: avoid; }
th, td { border: 0.3mm solid #666; padding: 1.4mm 2mm; vertical-align: top; text-align: left; }
th { background: #eef1f4; }
.watermark { position: fixed; top: 42%; left: 0; right: 0; text-align: center; font: 700 96pt "Segoe UI", Arial, sans-serif; color: rgba(160, 0, 0, 0.09); transform: rotate(-32deg); letter-spacing: 8mm; z-index: -1; }
.docfoot { margin-top: 8mm; padding-top: 2mm; border-top: 0.2mm solid #999; font: 7.5pt "Segoe UI", Arial, sans-serif; color: #555; text-align: left; }
"""


class GeneratorError(RuntimeError):
    """Generation failed. / Generování selhalo."""


def placeholders(text: str) -> set[str]:
    """Names of all {{variables}} in a template. / Názvy všech {{proměnných}} v šabloně."""
    return set(PLACEHOLDER.findall(text))


def fill(template: str, values: dict[str, str], name: str) -> str:
    """
    EN: Replace variables; fails on a missing, unused or non-string value and on malformed or unclosed braces.
    CZ: Nahradí proměnné; selže při chybějící, nepoužité či neřetězcové hodnotě a při chybných či neuzavřených závorkách.
    """
    if not isinstance(values, dict):
        raise GeneratorError(f"{name}: data must be a JSON object")
    stripped = ANY_BRACES.sub("", template)
    if "{{" in stripped or "}}" in stripped:
        raise GeneratorError(f"{name}: unclosed placeholder braces")
    needed = placeholders(template)
    malformed = [m for m in ANY_BRACES.findall(template) if not PLACEHOLDER.fullmatch(m)]
    if malformed:
        raise GeneratorError(f"{name}: malformed placeholders {sorted(set(malformed))}")
    missing = sorted(needed - set(values))
    unused = sorted(set(values) - needed)
    if missing:
        raise GeneratorError(f"{name}: missing values for {missing}")
    if unused:
        raise GeneratorError(f"{name}: data contain unused keys {unused}")
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise GeneratorError(f"{name}: value of {key} must be a non-empty string")
    return PLACEHOLDER.sub(lambda match: escape_value(values[match.group(1)]), template)


def escape_value(value: str) -> str:
    """
    EN: Make a data value inert before Markdown conversion: no HTML, no Markdown links/images/formatting, no line break.
    CZ: Zneškodní datovou hodnotu před převodem Markdownu: žádné HTML, žádné Markdown odkazy/obrázky/formátování ani zalomení řádku.
    """
    collapsed = " ".join(value.split())
    return _ESCAPE_RE.sub(lambda match: _ESCAPE_MAP[match.group(0)], collapsed)


def to_html(markdown_text: str, title: str, draft: bool, footer: str) -> str:
    """Render filled Markdown to a print-ready HTML page. / Vysází vyplněný Markdown do tiskové HTML stránky."""
    try:
        import markdown  # third-party dependency, see requirements.txt / externí závislost
    except ImportError as error:
        raise GeneratorError("Python package 'markdown' is not installed (pip install -r requirements.txt)") from error
    body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
    watermark = '<div class="watermark">VZOR</div>' if draft else ""
    return (f'<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{PAGE_CSS}</style></head><body>{watermark}{body}"
            f'<div class="docfoot">{html.escape(footer)}</div></body></html>')


def find_browser() -> str:
    """Locate a headless-capable Chromium browser. / Najde prohlížeč Chromium schopný headless tisku."""
    for candidate in BROWSER_CANDIDATES:
        if not candidate:
            continue
        if Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise GeneratorError("no Chrome / Edge / Chromium found (set POLARITA_PDF_BROWSER)")


def print_pdf(browser: str, html_path: Path, pdf_path: Path) -> None:
    """Print one HTML file to PDF without network access. / Vytiskne jeden HTML soubor do PDF bez přístupu k síti."""
    with tempfile.TemporaryDirectory() as profile:
        command = [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--disable-extensions",
                   "--host-resolver-rules=MAP * ~NOTFOUND", f"--user-data-dir={profile}",
                   f"--print-to-pdf={pdf_path}", html_path.as_uri()]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if completed.returncode != 0 or not pdf_path.is_file():
        raise GeneratorError(f"browser failed for {html_path.name}: {completed.stderr.strip()[-300:]}")


def validate_pdf(pdf_path: Path) -> int:
    """
    EN: Check the PDF signature and that no placeholder survived; returns the page count.
    CZ: Zkontroluje hlavičku PDF a že nezůstala žádná proměnná; vrátí počet stran.
    """
    raw = pdf_path.read_bytes()
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
        raise GeneratorError(f"{pdf_path.name} is not a valid PDF")
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise GeneratorError("Python package 'pypdf' is not installed (pip install -r requirements.txt)") from error
    reader = PdfReader(str(pdf_path))
    text = "".join(page.extract_text() or "" for page in reader.pages)
    if "{{" in text or "}}" in text:
        raise GeneratorError(f"{pdf_path.name} still contains an unfilled placeholder")
    if len(text.strip()) < 200:
        raise GeneratorError(f"{pdf_path.name} has almost no text")
    return len(reader.pages)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(template_dir: Path, only: str | None) -> list[Path]:
    """List templates and verify that all eight sets are present. / Vypíše šablony a ověří všech osm sestav."""
    templates = sorted(template_dir.glob("*.md"))
    if only:
        templates = [path for path in templates if path.stem == only]
        if not templates:
            raise GeneratorError(f"template {only} not found")
        return templates
    present = {path.name[:2] for path in templates}
    missing_sets = [prefix for prefix in REQUIRED_SETS if prefix not in present]
    if missing_sets:
        raise GeneratorError(f"missing templates for sets {missing_sets}")
    return templates


def generate(template_dir: Path, data_dir: Path, out_dir: Path, only: str | None, draft: bool, check_only: bool) -> list[dict[str, Any]]:
    """Generate all documents; returns one result record per template. / Vygeneruje dokumenty; vrátí záznam za šablonu."""
    templates = collect(template_dir, only)
    browser = None if check_only else find_browser()
    results: list[dict[str, Any]] = []
    shared_seen: set[str] = set()
    out_dir.mkdir(parents=True, exist_ok=True)
    for template_path in templates:
        name = template_path.stem
        data_path = data_dir / f"{name}.json"
        if not data_path.is_file():
            raise GeneratorError(f"{name}: data file {data_path.name} not found")
        template = template_path.read_text(encoding="utf-8")
        values = json.loads(data_path.read_text(encoding="utf-8"))
        if not template.startswith("# "):
            raise GeneratorError(f"{name}: template must start with a level-1 heading")
        filled = fill(template, values, name)
        shared_seen |= placeholders(template) & set(SHARED_VARIABLES)
        record: dict[str, Any] = {"template": template_path.name, "variables": len(values)}
        if not check_only:
            title = template.splitlines()[0][2:].strip()
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            if draft:
                footer = (f"VZOR s fiktivními daty — Polarita s.r.o. · šablona {template_path.name} · "
                          f"vygenerováno {stamp} · koncept ai podléhá kontrole 15001 a podpisu 1001")
            else:
                footer = f"Polarita s.r.o. · dokument {name} · vygenerováno {stamp}"
            pdf_path = out_dir / f"{name}.pdf"
            with tempfile.TemporaryDirectory() as tmp_html_dir:
                html_path = Path(tmp_html_dir) / f"{name}.html"
                html_path.write_text(to_html(filled, title, draft, footer), encoding="utf-8", newline="\n")
                print_pdf(browser or "", html_path, pdf_path)
            pages = validate_pdf(pdf_path)
            manifest = {
                "document": name,
                "title": title,
                "draft_watermark": draft,
                "generated_utc": stamp,
                "variables": values,
                "sha256": {"template": sha256(template_path), "data": sha256(data_path), "pdf": sha256(pdf_path)},
                "pages": pages,
            }
            (out_dir / f"{name}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                           encoding="utf-8", newline="\n")
            record.update({"pdf": pdf_path.name, "pages": pages})
        results.append(record)
    if not only:
        missing_shared = [var for var in SHARED_VARIABLES if var not in shared_seen]
        if missing_shared:
            raise GeneratorError(f"shared variables missing across templates: {missing_shared}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Polarita clean-copy PDF generator (package S1)")
    parser.add_argument("--template-dir", type=Path, default=TEMPLATE_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--only", help="template stem without .md, e.g. 07-predzalobni-vyzva")
    parser.add_argument("--final", action="store_true", help="omit the VZOR watermark (only after mutation_confirm)")
    parser.add_argument("--check", action="store_true", help="check templates and data without printing PDF")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        results = generate(args.template_dir, args.data_dir, args.output_dir, args.only, not args.final, args.check)
    except (GeneratorError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for item in results:
        suffix = f" -> {item['pdf']} ({item['pages']} pp.)" if "pdf" in item else f" ({item['variables']} vars OK)"
        print(f"OK {item['template']}{suffix}")
    print(f"VERIFIED_PASS: {len(results)}/{len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
