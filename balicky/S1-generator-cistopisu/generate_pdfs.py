# -*- coding: utf-8 -*-
"""
Generator of clean PDF copies of contracts and protocols (package S1, Version 3.20).
Generátor PDF čistopisů smluv a protokolů (balíček S1, Verze 3.20).

EN: Fills Markdown templates from sablony/ with variables from data/<same-name>.json,
    renders them to print HTML (A4) and prints PDF through a headless Chromium browser
    (Chrome / Edge). For every document it writes a manifest with the variables and SHA-256
    hashes of template, data and PDF — the input of the transactional diff "mutation_confirm".
    Exit code 0 is returned only when every template of all eight sets produced a valid PDF.
    The PDF is printed into a temporary file and replaces the previous one only after it passed
    validation (including the case number of the data), so a failed print never leaves or accepts
    an old document. Templates must be plain Markdown: raw HTML and variables inside code are refused.
    Validity protocol: a document is valid only as the pair <name>.pdf + <name>.manifest.json made by
    one successful run from the current inputs. Whenever a run for a document fails - its template or
    data are missing, cannot be read or do not pass validation, the print fails, or the printed PDF does
    not pass validation - the older pair of that document is removed (manifest first). One lock of the
    document is held from reading the inputs up to the withdrawal or the publication; while another run
    holds it, this run fails and touches nothing. A PDF without a manifest is an unfinished run and is
    never a basis for approval. --check validates only and never touches the outputs.
CZ: Vyplní Markdown šablony ze sablony/ proměnnými z data/<stejný-název>.json, vysází je do
    tiskového HTML (A4) a vytiskne PDF přes headless prohlížeč Chromium (Chrome / Edge).
    Ke každému dokumentu zapíše manifest s proměnnými a SHA-256 otisky šablony, dat a PDF —
    vstup transakčního diffu „mutation_confirm“. Návratový kód 0 se vrací pouze tehdy, když
    každá šablona všech osmi sestav vytvořila platné PDF.
    PDF se tiskne do dočasného souboru a předchozí nahradí až po úspěšné validaci (včetně čísla
    spisu z dat), takže nepovedený tisk nikdy nezanechá ani nepřijme starý dokument. Šablony musí
    být čistý Markdown: surové HTML a proměnné uvnitř kódu se odmítnou.
    Protokol platnosti: dokument platí jen jako dvojice <název>.pdf + <název>.manifest.json z jednoho
    úspěšného běhu nad aktuálními vstupy. Kdykoli běh pro dokument selže - šablona nebo data chybí,
    nelze je přečíst či neprojdou validací, tisk selže nebo vytištěné PDF neprojde validací - starší
    dvojice toho dokumentu se odstraní (manifest první). Jeden zámek dokumentu se drží od načtení vstupů
    až po stažení nebo zveřejnění; drží-li jej jiný běh, tento běh selže a na nic nesáhne. PDF bez
    manifestu je nedokončený běh a nikdy není podkladem pro schválení. --check jen validuje a na
    výstupy nesahá.

Usage / Použití:
    python generate_pdfs.py                      # all templates with sample data, watermark VZOR
    python generate_pdfs.py --check              # validate templates and data only / jen kontrola
    python generate_pdfs.py --only 07-predzalobni-vyzva --data-dir cesta/k/datum --final

Requires / Vyžaduje: Python packages "markdown" and "pypdf" (see requirements.txt) and Chrome or Edge.
"""

from __future__ import annotations

import argparse
import contextlib
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
RAW_HTML = re.compile(r"<[A-Za-z!/?][^>\n]*>|<(?:script|style|iframe|object|embed|img|svg|link|meta|base|form)\b", re.IGNORECASE)
CODE_WITH_PLACEHOLDER = re.compile(r"`[^`\n]*\{\{[^`\n]*`")
# EN: Markdown block markers at the start of a value (list, heading underline, rule, ordered list).
# CZ: Blokové značky Markdownu na začátku hodnoty (seznam, podtržení nadpisu, čára, číslovaný seznam).
LEADING_BLOCK_MARKER = re.compile(r"^(?:([-+=])|(\d{1,9})([.)]|&#41;))")
_LEADING_ENTITY = {"-": "&#45;", "+": "&#43;", "=": "&#61;", ".": "&#46;", ")": "&#41;", "&#41;": "&#41;"}
REQUIRE_BROWSER_ENV = "POLARITA_REQUIRE_BROWSER"
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


def check_template(template: str, name: str) -> None:
    """
    EN: A template is plain Markdown. Raw HTML would be passed to the browser as is (script, iframe, remote
        resources) and a variable inside a code span or code block would be printed with visible escapes.
    CZ: Šablona je čistý Markdown. Surové HTML by prošlo do prohlížeče beze změny (skript, iframe, vzdálené
        zdroje) a proměnná uvnitř kódu by se vytiskla s viditelnými escape sekvencemi.
    """
    fence = None
    for number, line in enumerate(template.splitlines(), 1):
        marker = re.match(r"^\s*(```|~~~)", line)
        if marker:
            fence = None if fence == marker.group(1) else (fence or marker.group(1))
            continue
        html_hit = RAW_HTML.search(line)
        if html_hit:
            raise GeneratorError(f"{name}: raw HTML is not allowed in a template (line {number}: {html_hit.group(0)[:40]})")
        if (fence or line.startswith(("    ", "\t"))) and "{{" in line or CODE_WITH_PLACEHOLDER.search(line):
            raise GeneratorError(f"{name}: placeholder inside code is not allowed (line {number})")


def fill(template: str, values: dict[str, str], name: str) -> str:
    """
    EN: Replace variables; fails on a missing, unused or non-string value and on malformed or unclosed braces.
    CZ: Nahradí proměnné; selže při chybějící, nepoužité či neřetězcové hodnotě a při chybných či neuzavřených závorkách.
    """
    if not isinstance(values, dict):
        raise GeneratorError(f"{name}: data must be a JSON object")
    check_template(template, name)
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
    # EN: Collapse ordinary white space only; non-breaking spaces ("86 450,00 Kč") are typography and stay.
    # CZ: Slučují se jen obyčejné bílé znaky; nezlomitelné mezery („86 450,00 Kč“) jsou typografie a zůstávají.
    collapsed = re.sub(r"[ \t\r\n\f\v]+", " ", value).strip(" ")
    escaped = _ESCAPE_RE.sub(lambda match: _ESCAPE_MAP[match.group(0)], collapsed)
    # EN: A value alone on a line must not become a list item, a heading underline or a rule.
    # CZ: Hodnota samotná na řádku se nesmí stát položkou seznamu, podtržením nadpisu ani čarou.
    marker = LEADING_BLOCK_MARKER.match(escaped)
    if marker:
        if marker.group(1):
            escaped = _LEADING_ENTITY[marker.group(1)] + escaped[1:]
        else:
            escaped = marker.group(2) + _LEADING_ENTITY[marker.group(3)] + escaped[marker.end():]
    return escaped


def to_html(markdown_text: str, title: str, draft: bool, footer: str) -> str:
    """Render filled Markdown to a print-ready HTML page. / Vysází vyplněný Markdown do tiskové HTML stránky."""
    try:
        import markdown  # third-party dependency, see requirements.txt / externí závislost
    except ImportError as error:
        raise GeneratorError("Python package 'markdown' is not installed (pip install -r requirements.txt)") from error
    body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
    watermark = '<div class="watermark">VZOR</div>' if draft else ""
    # EN: The policy forbids every load and every script; only the inline print style is allowed.
    # CZ: Politika zakazuje každé načtení i každý skript; povolen je jen vložený tiskový styl.
    policy = "default-src 'none'; style-src 'unsafe-inline'"
    return (f'<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{policy}"><title>{html.escape(title)}</title>'
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
    """
    EN: Print one HTML file to PDF without network access. pdf_path must not exist beforehand: the caller
        prints into a fresh temporary file, so a browser that exits with 0 without writing is detected.
    CZ: Vytiskne jeden HTML soubor do PDF bez přístupu k síti. pdf_path předem nesmí existovat: volající
        tiskne do nového dočasného souboru, takže prohlížeč, který skončí kódem 0 a nic nezapíše, se odhalí.
    """
    if pdf_path.exists():
        raise GeneratorError(f"internal error: print target {pdf_path.name} already exists")
    with tempfile.TemporaryDirectory() as profile:
        command = [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--disable-extensions",
                   "--host-resolver-rules=MAP * ~NOTFOUND", f"--user-data-dir={profile}",
                   f"--print-to-pdf={pdf_path}", html_path.as_uri()]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as error:
            raise GeneratorError(f"browser timed out for {html_path.name}") from error
    if completed.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise GeneratorError(f"browser failed for {html_path.name}: {completed.stderr.strip()[-300:]}")


def validate_pdf(pdf_path: Path, must_contain: str | None = None) -> int:
    """
    EN: Check the PDF signature, that no placeholder survived and that the text contains must_contain
        (the case number of the data - proof that this PDF was made from these data); returns the page count.
    CZ: Zkontroluje hlavičku PDF, že nezůstala žádná proměnná a že text obsahuje must_contain (číslo
        spisu z dat - důkaz, že toto PDF vzniklo z těchto dat); vrátí počet stran.
    """
    raw = pdf_path.read_bytes()
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
        raise GeneratorError(f"{pdf_path.name} is not a valid PDF")
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise GeneratorError("Python package 'pypdf' is not installed (pip install -r requirements.txt)") from error
    try:
        reader = PdfReader(str(pdf_path))
        text = "".join(page.extract_text() or "" for page in reader.pages)
    except Exception as error:  # pypdf raises several unrelated error types / pypdf vyhazuje více nesouvisejících typů chyb
        raise GeneratorError(f"{pdf_path.name} cannot be read as PDF: {error}") from error
    if "{{" in text or "}}" in text:
        raise GeneratorError(f"{pdf_path.name} still contains an unfilled placeholder")
    if len(text.strip()) < 200:
        raise GeneratorError(f"{pdf_path.name} has almost no text")
    if must_contain and "".join(must_contain.split()) not in "".join(text.split()):
        raise GeneratorError(f"{pdf_path.name} does not contain the case number {must_contain} of its data")
    return len(reader.pages)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invalidate(out_dir: Path, name: str) -> None:
    """
    EN: Withdraw the published pair of one document: the manifest (the commit record) first, then the PDF.
    CZ: Stáhne zveřejněnou dvojici jednoho dokumentu: nejdřív manifest (potvrzující záznam), pak PDF.
    """
    (out_dir / f"{name}.manifest.json").unlink(missing_ok=True)
    (out_dir / f"{name}.pdf").unlink(missing_ok=True)


def publish(out_dir: Path, name: str, staged_pdf: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    """
    EN: Publish one document as a pair PDF + manifest. The manifest is the commit record of the pair:
        it carries the hash of the STAGED PDF and is the last thing that appears, by an atomic rename.
        Order: (1) the old manifest is removed, (2) the staged PDF replaces the old one atomically,
        (3) the staged manifest is renamed in atomically. Two files cannot be switched by one system
        call, so the invariant is: a manifest that exists always describes the PDF next to it; an
        interrupted run leaves a PDF WITHOUT a manifest, never a PDF with a foreign or half-written one.
        Both staged files live in one unique staging folder inside out_dir (same file system).
    CZ: Zveřejní jeden dokument jako dvojici PDF + manifest. Manifest je potvrzujícím záznamem dvojice:
        nese otisk PŘIPRAVENÉHO PDF a objeví se jako poslední, atomickým přejmenováním. Pořadí: (1) starý
        manifest se odstraní, (2) připravené PDF atomicky nahradí staré, (3) připravený manifest se
        atomicky přejmenuje na místo. Dva soubory nelze přepnout jedním systémovým voláním, proto platí
        invariant: existující manifest vždy popisuje PDF vedle sebe; přerušený běh zanechá PDF BEZ
        manifestu, nikdy PDF s cizím nebo nedopsaným manifestem. Oba připravené soubory leží v jedné
        jedinečné přípravné složce uvnitř out_dir (stejný souborový systém).
    """
    pdf_path = out_dir / f"{name}.pdf"
    manifest_path = out_dir / f"{name}.manifest.json"
    staged_manifest = staged_pdf.with_name(f"{name}.manifest.json")
    if manifest["sha256"]["pdf"] != sha256(staged_pdf):
        raise GeneratorError(f"{name}: staged PDF does not match its manifest")
    with open(staged_manifest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        manifest_path.unlink(missing_ok=True)
        os.replace(staged_pdf, pdf_path)
        os.replace(staged_manifest, manifest_path)
    except OSError as error:
        manifest_path.unlink(missing_ok=True)
        raise GeneratorError(f"{name}: cannot publish the PDF and its manifest: {error}") from error
    return pdf_path, manifest_path


class _DocumentLock:
    """
    EN: One generation of one document into one folder at a time (exclusive lock file); two parallel
        runs could otherwise mix the data, the PDF and the hashes of different runs.
    CZ: Jedno generování jednoho dokumentu do jedné složky v jednom okamžiku (výlučný zámkový soubor);
        dva souběžné běhy by jinak mohly smíchat data, PDF a otisky různých běhů.
    """

    def __init__(self, out_dir: Path, name: str) -> None:
        self.path = out_dir / f".{name}.lock"
        self.name = name

    def __enter__(self) -> "_DocumentLock":
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise GeneratorError(f"{self.name}: another generation of this document is running (lock file {self.path.name}); "
                                 f"if no generator is running, delete the lock file and repeat") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return self

    def __exit__(self, *exc: object) -> None:
        self.path.unlink(missing_ok=True)


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


def withdraw_without_template(template_dir: Path, out_dir: Path, only: str | None) -> list[str]:
    """
    EN: A document whose template is gone has no current inputs, so its older pair is withdrawn too -
        under the lock of that document, exactly like any other invalid input. With --only it is the
        named document; in a full run every pair in out_dir whose manifest has no template. Only names
        with a manifest of this generator are touched (a foreign PDF in the folder is left alone) and
        a name that is not a plain file stem is ignored. Returns the names withdrawn.
    CZ: Dokument, jehož šablona zmizela, nemá aktuální vstupy, proto se jeho starší dvojice stáhne také -
        pod zámkem toho dokumentu, stejně jako při jiném vadném vstupu. S --only jde o jmenovaný
        dokument; při plném běhu o každou dvojici v out_dir, jejíž manifest nemá šablonu. Sahá se jen na
        názvy s manifestem tohoto generátoru (cizí PDF ve složce zůstane) a název, který není prostým
        názvem souboru, se ignoruje. Vrací stažené názvy.
    """
    if not out_dir.is_dir():
        return []
    stems = {path.stem for path in template_dir.glob("*.md")}
    suffix = ".manifest.json"
    if only:
        candidates = [only]
    else:
        candidates = sorted(path.name[:-len(suffix)] for path in out_dir.glob(f"*{suffix}"))
    withdrawn = []
    for name in candidates:
        if name in stems or not name or name.startswith(".") or Path(name).name != name or "\\" in name:
            continue
        if not (out_dir / f"{name}{suffix}").is_file():
            continue
        with _DocumentLock(out_dir, name):
            invalidate(out_dir, name)
        withdrawn.append(name)
    return withdrawn


def generate(template_dir: Path, data_dir: Path, out_dir: Path, only: str | None, draft: bool, check_only: bool) -> list[dict[str, Any]]:
    """Generate all documents; returns one result record per template. / Vygeneruje dokumenty; vrátí záznam za šablonu."""
    try:
        templates = collect(template_dir, only)
    except GeneratorError:
        # EN: A missing template is an invalid input as well: the older pair must not stay as valid.
        # CZ: Chybějící šablona je také vadný vstup: starší dvojice nesmí zůstat jako platná.
        if not check_only:
            withdraw_without_template(template_dir, out_dir, only)
        raise
    browser = None if check_only else find_browser()
    results: list[dict[str, Any]] = []
    shared_seen: set[str] = set()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not check_only and not only:
        withdraw_without_template(template_dir, out_dir, None)
    for template_path in templates:
        name = template_path.stem
        # EN: Validity protocol: a document is valid only as the pair PDF + manifest made by ONE successful
        #     run from the current inputs. As soon as the current inputs of a document cannot be read or
        #     do not pass validation, its older pair no longer describes the current state and is removed
        #     (manifest first) - exactly as after a failed print. --check never touches the outputs.
        #     ONE lock of the document is held from reading the inputs through validation up to the
        #     withdrawal or the publication, so a failing run can never delete or mix the output that
        #     another run is just producing under its lock; with the lock taken this run fails and
        #     touches nothing. --check takes no lock because it writes nothing.
        # CZ: Protokol platnosti: dokument platí jen jako dvojice PDF + manifest z JEDNOHO úspěšného běhu
        #     nad aktuálními vstupy. Jakmile aktuální vstupy dokumentu nejdou přečíst nebo neprojdou
        #     validací, jeho starší dvojice už aktuální stav nepopisuje a odstraní se (manifest první) -
        #     stejně jako po nepovedeném tisku. --check na výstupy nikdy nesahá.
        #     JEDEN zámek dokumentu se drží od načtení vstupů přes validaci až po stažení nebo zveřejnění,
        #     takže chybný běh nikdy nesmaže ani nesmíchá výstup, který jiný běh právě vyrábí pod svým
        #     zámkem; je-li zámek obsazen, tento běh selže a na nic nesáhne. --check zámek nebere,
        #     protože nic nezapisuje.
        with contextlib.ExitStack() as held:
            if not check_only:
                held.enter_context(_DocumentLock(out_dir, name))
            try:
                data_path = data_dir / f"{name}.json"
                if not data_path.is_file():
                    raise GeneratorError(f"{name}: data file {data_path.name} not found")
                # EN: Each source is read ONCE; the document and the hashes in the manifest come from the same bytes.
                # CZ: Každý zdroj se čte JEDNOU; dokument i otisky v manifestu vycházejí z týchž bajtů.
                try:
                    template_bytes = template_path.read_bytes()
                    data_bytes = data_path.read_bytes()
                    template = template_bytes.decode("utf-8")
                    values = json.loads(data_bytes.decode("utf-8"))
                except (OSError, ValueError) as error:  # unreadable, invalid UTF-8 or invalid JSON / nečitelné, neplatné UTF-8 nebo JSON
                    raise GeneratorError(f"{name}: cannot read template or data: {error}") from error
                if not template.startswith("# "):
                    raise GeneratorError(f"{name}: template must start with a level-1 heading")
                filled = fill(template, values, name)
            except GeneratorError:
                if not check_only:
                    invalidate(out_dir, name)
                raise
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
                # EN: The staging folder is unique and lies inside out_dir, so the final renames are atomic.
                # CZ: Přípravná složka je jedinečná a leží uvnitř out_dir, takže závěrečná přejmenování jsou atomická.
                with tempfile.TemporaryDirectory(prefix=f".{name}.staging-", dir=out_dir) as work_dir:
                    html_path = Path(work_dir) / f"{name}.html"
                    fresh_pdf = Path(work_dir) / f"{name}.pdf"
                    html_path.write_text(to_html(filled, title, draft, footer), encoding="utf-8", newline="\n")
                    try:
                        print_pdf(browser or "", html_path, fresh_pdf)
                        case_number = values.get("spis_id")
                        pages = validate_pdf(fresh_pdf, case_number if isinstance(case_number, str) else None)
                    except GeneratorError:
                        # EN: Never leave an older PDF or manifest next to a failed run - they would look current.
                        # CZ: Vedle nepovedeného běhu nikdy nenech starší PDF ani manifest - vypadaly by aktuálně.
                        invalidate(out_dir, name)
                        raise
                    manifest = {
                        "document": name,
                        "title": title,
                        "draft_watermark": draft,
                        "generated_utc": stamp,
                        "variables": values,
                        "sha256": {"template": hashlib.sha256(template_bytes).hexdigest(),
                                   "data": hashlib.sha256(data_bytes).hexdigest(), "pdf": sha256(fresh_pdf)},
                        "pages": pages,
                    }
                    publish(out_dir, name, fresh_pdf, manifest)
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
    except (GeneratorError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for item in results:
        suffix = f" -> {item['pdf']} ({item['pages']} pp.)" if "pdf" in item else f" ({item['variables']} vars OK)"
        print(f"OK {item['template']}{suffix}")
    print(f"VERIFIED_PASS: {len(results)}/{len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
