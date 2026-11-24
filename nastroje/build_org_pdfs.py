# -*- coding: utf-8 -*-
"""
Generátor tiskových PDF výstupů organizační struktury Polarita s.r.o. (Verze 3.18):
  1) 01-ORGANIZACNI-MAPA-A3-2026.pdf (1 strana A3 na šířku 420×297 mm, čitelná sazba bez zmenšení)
  2) 00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf (souborná Modrá kniha A4: Část 0–VI, 0× file:// URI, 1:1 měřítko)
Cesty jsou relativní k umístění skriptu (nastroje/ ve složce firemni-struktura/); HTML předlohy vznikají
v dočasné složce systému a do firemni-struktura/ se zapisují výhradně výsledná PDF.
Spuštění: python nastroje/build_org_pdfs.py   (vyžaduje balík markdown a Chrome nebo Edge)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote
import markdown

ROOT_STRUCT = Path(__file__).resolve().parents[1]
CANON = json.loads((Path(__file__).resolve().parent / "kanon.json").read_text(encoding="utf-8"))
VER = CANON["version"]
BUDGET_TOTAL = CANON["budget_total_usd"]
COMPANY = CANON["company"]
AGENTS_BY_ID = {agent["id"]: agent for agent in CANON["agents"]}
DEPT_BUDGETS = {
    dept: sum(agent["budget_usd"] for agent in CANON["agents"] if agent["department"] == dept)
    for dept in {agent["department"] for agent in CANON["agents"]}
}
ODD_DIR = ROOT_STRUCT / "oddeleni"
AG_DIR = ROOT_STRUCT / "agenti-a-prompty"

OUT_BOOK_PDF = ROOT_STRUCT / "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf"
OUT_POSTER_PDF = ROOT_STRUCT / "01-ORGANIZACNI-MAPA-A3-2026.pdf"

# EN: Browser candidates for headless printing: the POLARITA_PDF_BROWSER variable first, then usual
#     Windows paths, then command names found on PATH (Linux, macOS).
# CZ: Kandidáti na prohlížeč pro headless tisk: nejprve proměnná POLARITA_PDF_BROWSER, potom obvyklé
#     cesty ve Windows, potom názvy příkazů nalezené v PATH (Linux, macOS).
BROWSER_CANDIDATES = [
    os.environ.get("POLARITA_PDF_BROWSER", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def find_browser() -> Path:
    for candidate in BROWSER_CANDIDATES:
        if not candidate:
            continue
        if Path(candidate).is_file():
            return Path(candidate)
        found = shutil.which(candidate)
        if found:
            return Path(found)
    raise FileNotFoundError("Nebyl nalezen prohlížeč Chrome, Edge ani Chromium pro headless tisk PDF (nastav POLARITA_PDF_BROWSER).")


def doc_slug(rel_posix: str) -> str:
    return "doc-" + re.sub(r"[^A-Za-z0-9_-]+", "-", rel_posix).strip("-")


def github_slugify(value: str, separator: str = "-") -> str:
    """GitHub-compatible anchor slug preserving Czech diacritics."""
    return re.sub(r"[^\w\s-]", "", value.lower(), flags=re.UNICODE).strip().replace(" ", separator)


def sanitize_html_links(html: str, source_rel: str, included_rels: set[str]) -> str:
    """
    F32 fix: Nikdy nenechá v HTML relativní odkazy na lokální soubory, které by prohlížeč
    při tisku ze scratch/ přeložil na file:///C:/Users/... URI anotace.
    - Odkazy na dokumenty obsažené v této knize převede na interní PDF kotvy (#doc-...).
    - Vnitřní kotvy (#...) připne k prefixu dokumentu (#doc-...--kotva), aby se kapitoly nekolidovaly.
    - Odkazy na lokální soubory mimo tuto knihu převede na čistý textový štítek <span class="local-ref">.
    - Externí https:// / http:// / mailto: odkazy ponechá beze změny.
    """
    src_dir = (ROOT_STRUCT / source_rel).parent.resolve()
    root_res = ROOT_STRUCT.resolve()
    anchor_prefix = f"{doc_slug(source_rel)}--"

    def repl(match: re.Match) -> str:
        href = match.group(1).strip()
        inner = match.group(2)
        if href.startswith(("https://", "http://", "mailto:")):
            return match.group(0)
        if href.startswith("#"):
            return f'<a href="#{anchor_prefix}{href[1:]}">{inner}</a>'
        raw_path = unquote(href.split("#", 1)[0]).strip()
        if not raw_path:
            return inner
        try:
            resolved = (src_dir / raw_path).resolve()
            rel_posix = resolved.relative_to(root_res).as_posix()
        except Exception:
            return f'<span class="local-ref">{inner}</span>'
        if rel_posix in included_rels:
            return f'<a href="#{doc_slug(rel_posix)}">{inner}</a>'
        return f'<span class="local-ref">{inner}</span>'

    return re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', repl, html, flags=re.DOTALL)


def apply_canon_tokens(html: str) -> str:
    """Substitute canonical tokens from kanon.json into static poster/overview HTML templates."""
    replacements = {
        "__VER__": VER,
        "__BUDGET_TOTAL__": str(BUDGET_TOTAL),
        "__ICO__": COMPANY["ico"],
        "__DIC__": COMPANY["dic"],
        "__ISDS__": COMPANY["isds"],
        "__DOC_TOTAL__": str(CANON["documents"]["core_markdown"] + CANON["documents"]["core_pdf"]),
        "__DEPT12__": str(DEPT_BUDGETS["12"]),
        "__DEPT13__": str(DEPT_BUDGETS["13"]),
        "__DEPT14__": str(DEPT_BUDGETS["14"]),
        "__DEPT15__": str(DEPT_BUDGETS["15"]),
        "__DEPT16__": str(DEPT_BUDGETS["16"]),
        "__DEPT17__": str(DEPT_BUDGETS["17"]),
        "__DEPT18__": str(DEPT_BUDGETS["18"]),
    }
    for agent_id, agent in AGENTS_BY_ID.items():
        replacements[f"__BUDGET_{agent_id}__"] = str(agent["budget_usd"])
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html


def build_poster_html() -> str:
    template = r"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<title>Polarita s.r.o. — Architektura hybridní ai-first společnosti · Verze __VER__ (A3)</title>
<style>
  @page {
    size: 420mm 297mm;
    margin: 0;
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  html, body {
    width: 420mm;
    height: 297mm;
    max-width: 420mm;
    max-height: 297mm;
    background: #f8fafc;
    color: #0f172a;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
    font-size: 6.6pt;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    overflow: hidden;
  }
  code {
    font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
    font-size: 6.2pt;
    background: #f1f5f9;
    color: #0f172a;
    border: 0.2mm solid #cbd5e1;
    border-radius: 0.8mm;
    padding: 0.03mm 0.65mm;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .canvas {
    width: 420mm;
    height: 297mm;
    padding: 3.6mm 4.6mm 3.6mm 4.6mm;
    display: flex;
    flex-direction: column;
    gap: 1.6mm;
    background: #f8fafc;
    overflow: hidden;
  }

  /* 1. TOP DARK HEADER */
  .topbar {
    background: linear-gradient(100deg, #091929 0%, #0d2e47 58%, #0f445e 100%);
    color: #ffffff;
    border-radius: 2.3mm;
    padding: 2.0mm 3.8mm;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 3.5mm;
    flex-shrink: 0;
  }
  .top-left h1 {
    font-size: 12.6pt;
    font-weight: 800;
    letter-spacing: -0.01em;
    color: #ffffff;
    line-height: 1.14;
  }
  .top-left .sub {
    font-size: 6.9pt;
    color: #7dd3fc;
    margin-top: 0.35mm;
    font-weight: 600;
  }
  .top-left .sub span.em {
    color: #6ee7b7;
  }
  .top-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.9mm;
    flex-shrink: 0;
  }
  .pill-row {
    display: flex;
    gap: 1.3mm;
    align-items: center;
  }
  .hpill {
    font-size: 6.5pt;
    font-weight: 600;
    padding: 0.38mm 1.9mm;
    border-radius: 99mm;
    background: rgba(255, 255, 255, 0.09);
    border: 0.25mm solid rgba(125, 211, 252, 0.35);
    color: #f0f9ff;
    white-space: nowrap;
  }
  .hpill.accent {
    background: rgba(16, 185, 129, 0.18);
    border-color: rgba(110, 231, 183, 0.5);
    color: #d1fae5;
  }

  /* 2. UPPER 3-BOX GOVERNANCE TIER */
  .upper-tier {
    display: grid;
    grid-template-columns: 129mm 11.5mm 134mm 11.5mm 124.8mm;
    align-items: stretch;
    flex-shrink: 0;
  }
  .u-card {
    border-radius: 2.1mm;
    padding: 1.55mm 2.5mm;
    background: #ffffff;
    border: 0.36mm solid #cbd5e1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
  }
  .u-card.amber { background: #fffdf7; border-color: #f59e0b; }
  .u-card.blue { background: #f4faff; border-color: #0284c7; }
  .u-card.emerald { background: #f3fcf8; border-color: #10b981; }
  .u-eyebrow {
    font-size: 6.1pt;
    font-weight: 800;
    letter-spacing: 0.03em;
    margin-bottom: 0.25mm;
  }
  .u-card.amber .u-eyebrow { color: #b45309; }
  .u-card.blue .u-eyebrow { color: #0369a1; }
  .u-card.emerald .u-eyebrow { color: #047857; }
  .u-title {
    font-size: 7.9pt;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 0.45mm;
    line-height: 1.15;
  }
  .u-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.35mm;
  }
  .u-list li {
    font-size: 6.45pt;
    line-height: 1.2;
    color: #1e293b;
    padding-left: 1.8mm;
    position: relative;
  }
  .u-list li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: #64748b;
    font-weight: 800;
  }
  .u-conn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 0.3mm;
    padding: 0 0.3mm;
  }
  .u-conn .c-lbl { font-size: 6.0pt; font-weight: 800; color: #0369a1; line-height: 1.14; }
  .u-conn.em .c-lbl { color: #047857; }
  .u-conn .c-arr { font-size: 10.2pt; font-weight: 900; color: #0284c7; line-height: 1; }
  .u-conn.em .c-arr { color: #059669; }

  /* 3. MIDDLE 7-COLUMN DEPARTMENT GRID (12-18) */
  .cols-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1.75mm;
    flex: 1;
    min-height: 0;
  }
  .col {
    background: #ffffff;
    border: 0.32mm solid #cbd5e1;
    border-radius: 2.0mm;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }
  .col-head {
    padding: 1.25mm 1.85mm;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8mm;
    flex-shrink: 0;
  }
  .col-head h3 { font-size: 7.0pt; font-weight: 800; line-height: 1.13; }
  .col-badge {
    font-size: 6.0pt;
    font-weight: 700;
    padding: 0.22mm 1.15mm;
    border-radius: 99mm;
    background: rgba(255, 255, 255, 0.22);
    white-space: nowrap;
    flex-shrink: 0;
  }
  .col-sub {
    padding: 0.65mm 1.65mm;
    font-size: 6.15pt;
    color: #334155;
    background: #f8fafc;
    border-bottom: 0.24mm solid #e2e8f0;
    line-height: 1.15;
    flex-shrink: 0;
  }
  .col-body {
    padding: 0.95mm 1.35mm;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 0.8mm;
    flex: 1;
    min-height: 0;
  }
  .mcard {
    border: 0.25mm solid #cbd5e1;
    border-radius: 1.45mm;
    padding: 0.85mm 1.3mm;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    gap: 0.22mm;
    flex: 1 1 auto;
  }
  .mcard.human { background: #f4fdf8; border-color: #86efac; }
  .mcard.alert { background: #fffbeb; border-color: #f59e0b; }
  .mcard.summary { background: #f8fafc; border-style: dashed; border-color: #94a3b8; }
  .mcard-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5mm;
  }
  .mcard-title { font-size: 6.65pt; font-weight: 800; color: #0f172a; line-height: 1.13; }
  .pill-grp {
    display: flex;
    align-items: center;
    gap: 0.4mm;
    flex-shrink: 0;
  }
  .mtag {
    font-size: 5.75pt;
    font-weight: 700;
    padding: 0.1mm 0.75mm;
    border-radius: 0.8mm;
    background: #eff6ff;
    color: #1d4ed8;
    border: 0.18mm solid #bfdbfe;
    white-space: nowrap;
  }
  .mtag.ai { background: #f1f5f9; color: #334155; border-color: #cbd5e1; }
  .mtag.id { background: #f8fafc; color: #0f172a; border-color: #cbd5e1; font-family: Consolas, monospace; }
  .mtag.usd { background: #eff6ff; color: #0369a1; border-color: #bae6fd; }
  .mtag.hum { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
  .mtag.sec { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
  .mcard-role { font-size: 6.2pt; font-weight: 700; color: #1e293b; line-height: 1.13; }
  .mcard-desc { font-size: 6.05pt; color: #334155; line-height: 1.17; }
  .col-foot {
    padding: 0.75mm 1.55mm;
    background: #f8fafc;
    border-top: 0.24mm solid #e2e8f0;
    font-size: 6.0pt;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.14;
    flex-shrink: 0;
  }

  .c-purple  .col-head { background: #4f46e5; }
  .c-teal    .col-head { background: #0d9488; }
  .c-sky     .col-head { background: #0284c7; }
  .c-crimson .col-head { background: #be123c; }
  .c-amber   .col-head { background: #d97706; }
  .c-slate   .col-head { background: #1e293b; }
  .c-green   .col-head { background: #15803d; }

  /* 4. BOTTOM 2-BOX STRIP */
  .bottom-strip {
    display: grid;
    grid-template-columns: 222mm 1fr;
    gap: 2.0mm;
    flex-shrink: 0;
  }
  .b-flow {
    background: #0b1f33;
    color: #f8fafc;
    border-radius: 2.1mm;
    padding: 1.5mm 2.6mm;
    display: flex;
    flex-direction: column;
    gap: 0.42mm;
  }
  .b-flow h4 { font-size: 6.65pt; font-weight: 800; color: #7dd3fc; letter-spacing: 0.025em; }
  .b-flow p { font-size: 6.1pt; line-height: 1.19; color: #e2e8f0; }
  .b-flow code {
    background: rgba(255, 255, 255, 0.13);
    color: #ffffff;
    border-color: rgba(125, 211, 252, 0.35);
    font-size: 5.95pt;
  }
  .b-rules {
    background: #fffafa;
    border: 0.34mm solid #fecdd3;
    border-radius: 2.1mm;
    padding: 1.5mm 2.5mm;
    display: flex;
    flex-direction: column;
    gap: 0.4mm;
  }
  .b-rules h4 { font-size: 6.65pt; font-weight: 800; color: #be123c; letter-spacing: 0.025em; }
  .b-rules p { font-size: 6.05pt; line-height: 1.18; color: #1e293b; }
</style>
</head>
<body>
<div class="canvas">

  <!-- 1. TOP DARK HEADER -->
  <header class="topbar">
    <div class="top-left">
      <h1>POLARITA S.R.O. — ARCHITEKTURA HYBRIDNÍ ai-first SPOLEČNOSTI · VERZE __VER__ (2026)</h1>
      <div class="sub">
        <span class="em">Zelená louka · Elektro WMS polarita.eu · 360° Karta „Pracuj“ · Asterisk + WhisperX + Silero VAD + librosa + Zulip + Stalwart + Chatwoot</span> · Bloky 0–12 (Týdny 0–12) + Bloky 13–19 (S1–S7)
      </div>
    </div>
    <div class="top-right">
      <div class="pill-row">
        <span class="hpill">IČO: __ICO__ · DIČ: __DIC__ · ISDS: __ISDS__ (16002) · Pobočka 101</span>
        <span class="hpill accent">2c Útvar (11–99) · 3c Pobočka (101+) · 4c Člověk (1001+) · ORG-* · 5c ai (11001+)</span>
      </div>
      <div class="pill-row">
        <span class="hpill">polarita-hq (Ubuntu LTS · Incus · 6+9 PG DB + PgBouncer · 0× MySQL/MongoDB)</span>
        <span class="hpill">20 ai = __BUDGET_TOTAL__ USD/m (85 % + 15 % P1) · Stage 1/2 Eval 20/20</span>
      </div>
    </div>
  </header>

  <!-- 2. UPPER 3-BOX GOVERNANCE TIER -->
  <section class="upper-tier">
    <div class="u-card amber">
      <div class="u-eyebrow">ÚTVAR 11 · STUPEŇ 1 · STATUTÁRNÍ ORGÁN, VLASTNÍK &amp; ODBORNÝ GARANT ELEKTRO (ČLOVĚK)</div>
      <div class="u-title">1001 · Václav Šercl · člověk · <code>STAT-1001</code> · TIČR E2A</div>
      <ul class="u-list">
        <li>Pobočka <code>101</code> (Praha 2) · <code>Decisions</code> (<code>URGENT</code> vs. <code>07:30/16:30</code> diff <code>mutation_confirm</code>) + YubiKey · odpovědnost účetní jednotky (+ smluvní <code>ORG-UOL</code>)</li>
        <li>Odborný garant elektro (10leté <code>Oprávnění</code> TIČR + 5leté <code>Osvědčení</code> RT), předseda <strong>3čl. zkušební komise</strong> + <code>Break-Glass</code> (<code>SUB-1007</code> pod vl. TIČR + vl. klíč zástupce; YubiKey č. 2 jen pro <code>1001</code>)</li>
        <li>Osobní kvalifikovaný podpis <code>QES</code> (<code>JSignPdf</code> na čipu <code>QSCD</code>) smluv, revizí, pasů rozváděčů dle platné normy, DSPS a odeslání z ISDS <code>w9bbdva</code></li>
      </ul>
    </div>

    <div class="u-conn">
      <div class="c-lbl">Dual-Control</div>
      <div class="c-arr">⇄</div>
      <div class="c-lbl">07:30 / 16:30</div>
    </div>

    <div class="u-card blue">
      <div class="u-eyebrow">ÚTVAR 11 · STUPEŇ 2 · VÝKONNÝ ŘEDITEL PROVOZU A HLAVNÍ KOORDINÁTOR (11001 · 35 USD/M)</div>
      <div class="u-title">11001 · Marek Kovář · ai · ID: <code>ceo</code></div>
      <ul class="u-list">
        <li>Ploché řízení 19 ai v 7 odděleních (<code>12–18</code>) + živého týmu <code>1002+</code> v tématech <code>Zulip</code> (<code>#kanál -&gt; POL-RRRR-NNNNN</code>, kanonický <code>case_id</code> + <code>branch_id</code>)</li>
        <li>Řídí <strong>360° Kartu spisu</strong>, matici zdrojů dle úkolu, <code>Decisions</code>, <strong>Pojistnou matici</strong> a <strong>Partnerský ledger 100 % + 10–15 % MRR</strong></li>
        <li>Pojistka zacyklení: max. 15 kroků / 2 opravy → <code>FAIL_CLOSED</code> · při neobsazené nepřítomnosti (&lt; 10 d) přepíná ISDS API do <code>PAUSED</code> (fikce doručení)</li>
      </ul>
    </div>

    <div class="u-conn em">
      <div class="c-lbl">Běží na</div>
      <div class="c-arr">→</div>
      <div class="c-lbl">Linux LTS</div>
    </div>

    <div class="u-card emerald">
      <div class="u-eyebrow">ČISTÝ FYZICKÝ SERVER · UBUNTU LTS · CELÁ FIRMA V INCUS · 6+9 PG DB + PGBOUNCER</div>
      <div class="u-title">Server <code>polarita-hq</code> · Kořen <code>/srv/polarita/</code> · Acyklické Bloky 0–12</div>
      <ul class="u-list">
        <li>4 zóny: <code>dmz_edge</code> (Caddy + <code>3478/udp</code> + MX <code>25/tcp</code>, <code>0</code> SIP) · <code>app_internal</code> (storefronty + <code>Asterisk</code>, <code>Zulip</code>, <code>Chatwoot</code> (veřejně jen widget a webhooky kanálů, vše ostatní za VPN + <code>oauth2-proxy</code>)) · <code>data_vault</code> (<code>6+9 PG DB + PgBouncer</code> + OpenBao) · <code>sandbox_airgap (eth0 none)</code></li>
        <li><code>Headscale VPN</code> · <code>Clean Room</code> (0 HR karet ve Vaultu) + <code>Kanál R FAIL_CLOSED</code> · <code>Restic REST Server (--append-only)</code> + watchdog (nedělní + čtvrtletní Full DR Drill)</li>
      </ul>
    </div>
  </section>

  <!-- 3. MIDDLE 7-COLUMN DEPARTMENT GRID (12-18) -->
  <main class="cols-grid">

    <!-- COL 12 -->
    <section class="col c-purple">
      <div class="col-head">
        <h3>12 · Marketing &amp; ai Růst</h3>
        <span class="col-badge">2 ai · 45 $</span>
      </div>
      <div class="col-sub">Reklama na marži <strong>POAS</strong> + Kalkulačka SVJ a GEO citace.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">12001 · Tomáš Dvořák</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">marketing</span><span class="mtag usd">25 $</span></span>
          </div>
          <div class="mcard-role">Manažer výkonnostní reklamy a kampaní</div>
          <div class="mcard-desc">Google/Meta/Sklik přes <code>polarita-ads-mcp</code> (zámek <code>PAUSED</code> + Spend Cap), Heureka/Zboží, Ecomail (zákazníci vs. souhlas), <code>Umami</code> + atribuce hovorů <code>Asterisk</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">12002 · Klára Novotná</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">obsah-geo</span><span class="mtag usd">20 $</span></span>
          </div>
          <div class="mcard-role">Specialistka obsahu, SEO, GEO a recenzí</div>
          <div class="mcard-desc">Správa <code>llms.txt</code>, <code>JSON-LD</code> a Kalkulačky SVJ (<code>/kalkulacka-svj</code>), FAQ z anonymizovaných dotazů (ověřené <code>15002</code>); jmenné reference jen se souhlasem klienta + <code>1001</code>.</div>
        </div>
        <div class="mcard summary">
          <div class="mcard-role">Pásma POAS &amp; Brand Safety (F34)</div>
          <div class="mcard-desc">Cíl POAS e-shop ≥ 1,8× / služby ≥ 3,0× · varování &lt; 1,8× · tvrdý stop kampaně &lt; 1,5× za 7 dní · kreativní grafika <code>ArtCraft</code> (mimo CAD).</div>
        </div>
      </div>
      <div class="col-foot">Cíl POAS ≥ 1,8× / 3,0× · stop &lt; 1,5× · 0 aktivací bez PAUSED</div>
    </section>

    <!-- COL 13 -->
    <section class="col c-teal">
      <div class="col-head">
        <h3>13 · E-shop, WMS &amp; Nákup</h3>
        <span class="col-badge">2 ai · 45 $</span>
      </div>
      <div class="col-sub">Provoz <strong>polarita.eu</strong>, sklad <strong>Elektro WMS</strong>, B2B nákup a tendry.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">13001 · Jakub Černý</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">eshop</span><span class="mtag usd">25 $</span></span>
          </div>
          <div class="mcard-role">Manažer e-shopu polarita.eu, Elektro WMS a RMA</div>
          <div class="mcard-desc">Rezervace staveb, bubny, <code>S/N</code>, <code>Return-to-Stock</code>, PHE, pasy baterií pro LMT, EV a průmyslové baterie &gt; 2 kWh (od 18. 2. 2027), <code>SCRAP-CU</code> (přenesená daň), zámek platné normy rozváděčů, import se souhlasem <code>1001</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">13002 · Petra Veselá</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">nakupci</span><span class="mtag usd">20 $</span></span>
          </div>
          <div class="mcard-role">Manažerka nákupu, doplňování VAN-* a tendrů</div>
          <div class="mcard-desc">Doplňování <code>VAN-101-xx</code>, <strong>3-Way Match</strong> + ISDOC, prověrka ADIS (ručení za DPH) / ISIR / ARES, 3 nabídky &gt; 50 tis. Kč (neskladové &gt; 20 tis.) a sken NEN/EZAK.</div>
        </div>
        <div class="mcard summary">
          <div class="mcard-role">Přesné lhůty RMA &amp; Tendrů (F26, F34)</div>
          <div class="mcard-desc">RMA 30 dnů běží od neměnného <code>complaint_asserted_at</code> (spotřebitel) · tendry NEN: cíl ≥ 7 d, stop &lt; 4 prac. dny.</div>
        </div>
      </div>
      <div class="col-foot">Expedice ≤ 24 h · QR inventura 1× týd. · RMA 30 d od uplatnění</div>
    </section>

    <!-- COL 14 -->
    <section class="col c-sky">
      <div class="col-head">
        <h3>14 · Elektro, Projekce, ÚRS &amp; Revize</h3>
        <span class="col-badge">5 ai · 140 $</span>
      </div>
      <div class="col-sub">Inženýring a Akademie pod garancí <code>1001</code> (TIČR E2A).</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">14001 · Pavel Horák</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">projektant</span><span class="mtag usd">40 $</span></span>
          </div>
          <div class="mcard-role">Specialista elektroprojekce a schémat QElectroTech</div>
          <div class="mcard-desc"><code>QElectroTech</code> (<code>.qet</code>) + <code>LibreDWG/ezdxf</code> (+ pilot <code>CadCraft</code>), Pas rozváděče dle platné normy + výpočet oteplení, zámek <code>DTM ČR</code> a podpisová brána DSPS.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">14002 · Radek Beneš</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">rozpoctar</span><span class="mtag usd">30 $</span></span>
          </div>
          <div class="mcard-role">Přípravář a rozpočtář zakázek (CS ÚRS a vícepráce)</div>
          <div class="mcard-desc">Rozpočty <code>.xc4/.xlsx</code>; 9 vrstev přípomocí CS ÚRS; Změnové listy víceprací spárované s důkazním hovorem <code>#t=MM:SS LEGAL_HOLD</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">14003 · Lukáš Král</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">revizak</span><span class="mtag usd">25 $</span></span>
          </div>
          <div class="mcard-role">Příprava kladných i negativních revizních zpráv</div>
          <div class="mcard-desc">Návrhy revizí z měření RT <code>1001</code> / <code>SUB-1007</code> (vč. negativní <code>NESCHOPNO</code> při překročení norem), hlasový <code>Stavební deník</code>, <code>48h šanony</code> a 3úrovňové <code>OCPP</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">14004 · Martin Pokorný</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">skolitel</span><span class="mtag usd">25 $</span></span>
          </div>
          <div class="mcard-role">Koordinátor Elektro Akademie (Moodle LTS)</div>
          <div class="mcard-desc">Poučení osoby poučené (bez komise, ≤ 3 r.) vs. zkoušky elektrotechniků před 3čl. komisí, trenažér RT TIČR a síť <strong>Certified Partner SUB</strong> (<code>10–15 % MRR</code>).</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">14005 · Lucie Krejčová</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">zakazky</span><span class="mtag usd">20 $</span></span>
          </div>
          <div class="mcard-role">360° Karta spisu „Pracuj“, WebRTC a Lhůtník</div>
          <div class="mcard-desc">Událostní webhook <code>comm-gateway</code> (SLA &lt; 30 m Po–Pá 07–17 h + 15m záloha), urgence <code>Silero VAD + librosa</code> (jen <code>Kanál L</code>), <code>Mapy.cz</code>, matice zdrojů a Lhůtník.</div>
        </div>
      </div>
      <div class="col-foot">SLA: Poptávka &lt; 30 m · revize ≤ 4 h · šanony ≤ 48 h</div>
    </section>

    <!-- COL 15 -->
    <section class="col c-crimson">
      <div class="col-head">
        <h3>15 · Právo &amp; Normy ČSN</h3>
        <span class="col-badge">2 ai · 60 $</span>
      </div>
      <div class="col-sub">Nezávislí Verifikátoři (<strong>Worker / Judge</strong>) s blokačním vetem.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">15001 · Tereza Jelínková</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">pravni-specialista</span><span class="mtag usd">30 $</span></span>
          </div>
          <div class="mcard-role">Smluvní, pracovněprávní a GDPR kontrola</div>
          <div class="mcard-desc">SoD, MRR, přednástupní JMHZ, odpovědnost za <code>VAN-*</code> / měřidla / <strong>vozidla (obecná)</strong>, IVR s poučením GDPR, zákaz emocí <code>Kanál R</code>, ručení za DPH &amp; předžalobní výzva.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">15002 · Zdeněk Fiala</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">normovac</span><span class="mtag usd">30 $</span></span>
          </div>
          <div class="mcard-role">Metodik normové báze (Vault) a metrologie</div>
          <div class="mcard-desc">Normová báze <code>03-Normy-a-Metodiky/</code> (práce na el. zařízeních, instalace, rozváděče NN, regály, sítě <code>DTM ČR</code>), 5leté Osvědčení RT vs. 10leté Oprávnění TIČR.</div>
        </div>
        <div class="mcard summary">
          <div class="mcard-role">Čistý kontext Judge (wt-judge)</div>
          <div class="mcard-desc">Judge běží na odlišné rodině modelu než Worker a dostává výhradně Zadání, artefakt a výstup testů — nikdy obhajobu tvůrce.</div>
        </div>
      </div>
      <div class="col-foot">0 zrušených norem u nové výroby · 0 emocí na Kanálu R · veto ≤ 2 h</div>
    </section>

    <!-- COL 16 -->
    <section class="col c-amber">
      <div class="col-head">
        <h3>16 · Finance &amp; Kancelář</h3>
        <span class="col-badge">2 ai · 40 $</span>
      </div>
      <div class="col-sub">Fakturace, ADIS, ORG-UOL, ISDS w9bbdva &amp; Asterisk.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">16001 · Eva Kučerová</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">ucetni</span><span class="mtag usd">25 $</span></span>
          </div>
          <div class="mcard-role">Finanční kontrolorka, ADIS, 3-Way Match a UOL</div>
          <div class="mcard-desc">ADIS (ručení za DPH), DB mutex řad, přenesená daň, PHE, ISDOC/Peppol, EET 2.0, <code>+3/+10/+20 d</code>, MRR ledger; mzdy audit 2. prac. den do 17:00 → smluvní <code>ORG-UOL</code> 3. den.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">16002 · Anna Sedláčková</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">tajemnik</span><span class="mtag usd">15 $</span></span>
          </div>
          <div class="mcard-role">Tajemnice, recepce Asterisk, Stalwart a Podatelna ISDS</div>
          <div class="mcard-desc"><code>Asterisk</code> (IVR, stereo <code>90d</code> / <code>LEGAL_HOLD</code>), <code>WhisperX</code>, <code>Stalwart</code>, <code>Chatwoot CE</code>, 8cestný <code>comm-gateway</code> a ISDS <code>w9bbdva</code> (<code>Po–Pá 06:50</code> jen při službě <code>1001</code> / <code>Break-Glass</code>, jinak <code>PAUSED</code>!).</div>
        </div>
        <div class="mcard summary">
          <div class="mcard-role">Právní pojistka ISDS &amp; účetnictví (F01, F08)</div>
          <div class="mcard-desc"><code>GetListOfReceivedMessages</code> má u zpráv v rozsahu oprávnění účtu doručovací účinek (doručení přihlášením) — testy jen na <code>czebox.cz</code>! Odpovědnost účetní jednotky drží <code>1001</code>.</div>
        </div>
      </div>
      <div class="col-foot">ISDS 06:50 (služba) / PAUSED · Zmešk. SMS ≤ 2 m · Mzdy 2.–3. den</div>
    </section>

    <!-- COL 17 -->
    <section class="col c-slate">
      <div class="col-head">
        <h3>17 · IT, Vývoj, Bezpečnost &amp; ai</h3>
        <span class="col-badge">5 ai · 85 $</span>
      </div>
      <div class="col-sub">Server <code>polarita-hq</code>, 10 modulů, Zulip, Clean Room a OpenBao.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">17001 · Ondřej Němec</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">programator</span><span class="mtag usd">35 $</span></span>
          </div>
          <div class="mcard-role">Hlavní vývojář 10 vlastních modulů a jader</div>
          <div class="mcard-desc"><code>metadata-schema-kernel</code> (jen vlastní schémata v <code>db_erp_lhutnik</code>), <code>cz-sk-registry-kernel</code>, <code>comm-gateway</code>, <code>polarita-ads-mcp</code>, <code>cad-urs-engine</code>, WMS.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">17002 · Filip Urban</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">webmaster</span><span class="mtag usd">15 $</span></span>
          </div>
          <div class="mcard-role">Správce webů, WebRTC softphonu a 360° Karty</div>
          <div class="mcard-desc">360° Karta „Pracuj“ + <code>WebRTC/Linphone</code> + <code>#t=MM:SS</code>, Kalkulačka SVJ, <code>Chatwoot</code> WebChat, QR <code>/objekt/</code>, <code>polarita.eu</code>, PWA a <code>Umami</code> nad PG.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">17003 · Michal Vlček</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">spravce-site</span><span class="mtag usd">15 $</span></span>
          </div>
          <div class="mcard-role">Správce Ubuntu LTS, Incus/OpenTofu, PBX a 6+9 PG DB + PgBouncer</div>
          <div class="mcard-desc"><code>Incus + OpenTofu</code>, 4 zóny (<code>eth0 none</code>), <code>Asterisk</code>, <code>Zulip</code> (Blok 7), <code>Stalwart</code>, <code>Chatwoot</code> (veřejně jen widget a webhooky kanálů, vše ostatní za VPN + <code>oauth2-proxy</code>), <code>6+9 PG DB</code>, Checkmk + watchdog a 2× DR drill.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">17004 · Roman Hájek</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">klicnik</span><span class="mtag usd">10 $</span></span>
          </div>
          <div class="mcard-role">Kyberbezpečnost, OpenBao, 3vrstvý CaMeL a QES/pečeť</div>
          <div class="mcard-desc">OpenBao + TPM + YubiKey, <code>Clean Room</code> (0 PII ve Vaultu), oddělení osobního <code>QES</code> (čip <code>QSCD</code>) od serverové pečeti <code>pyHanko</code>, 3vrstvý <code>CaMeL</code> a <code>AigisCode</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">17005 · Viktor Šimek</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">ai-provoz</span><span class="mtag usd">10 $</span></span>
          </div>
          <div class="mcard-role">Paperclip, Zulip boti, FinOps __BUDGET_TOTAL__ USD a Eval Stage 1/2</div>
          <div class="mcard-desc">Strop <code>__BUDGET_TOTAL__ USD/m</code> (<code>85 %</code> provoz + <code>15 % P1</code> rezerva, <code>100 % = tvrdý stop</code>), 1 zdroj promptů v Gitea, <code>wt-worker/judge</code> a dvoustupňová <code>Eval Suite</code> (<code>Stage 1 &amp; 2</code>; <code>Promptfoo</code> s modelem mimo CI).</div>
        </div>
      </div>
      <div class="col-foot">SLA ≥ 99,9 % · Stage 1 &amp; 2 Eval 20/20 · Strop ≤ __BUDGET_TOTAL__ USD/m</div>
    </section>

    <!-- COL 18 -->
    <section class="col c-green">
      <div class="col-head">
        <h3>18 · Lidé, HR, BOZP &amp; Realizace</h3>
        <span class="col-badge">1 ai · 20 $ + Lidé</span>
      </div>
      <div class="col-sub">Živý tým (<code>1002+</code>), přednástupní JMHZ a flotila.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">18001 · Šárka Benešová</span>
            <span class="pill-grp"><span class="mtag ai">ai</span><span class="mtag id">personalista</span><span class="mtag usd">20 $</span></span>
          </div>
          <div class="mcard-role">Evidence osob, přednástupní JMHZ, pravidla sledování a flotila</div>
          <div class="mcard-desc">Jediný záznam karet v <code>db_hr_lide</code> (<code>0</code> ve Vaultu, <code>0</code> skenů OP), uzávěrka mezd 2. prac. den do 12:00, matice zdrojů dle úkolu + <code>Mapy.cz</code> a <code>fleet-gps-bridge</code>.</div>
        </div>
        <div class="mcard human">
          <div class="mcard-top">
            <span class="mcard-title">EMP · Zaměstnanci HPP / částečný</span>
            <span class="pill-grp"><span class="mtag hum">člověk</span><span class="mtag id">EMP-1002+</span></span>
          </div>
          <div class="mcard-role">Vedoucí elektrotechnik · Elektrotechnik · Skladník (poučený)</div>
          <div class="mcard-desc">Rozvrh směn <strong>≥ 14 dnů předem</strong>, PLS, odpovědnost za měřidla, <code>VAN-*</code> a <strong>vozidla (obecná)</strong>, diktování deníku <code>WhisperX</code> &amp; <code>Zulip</code>.</div>
        </div>
        <div class="mcard human">
          <div class="mcard-top">
            <span class="mcard-title">BRI · Brigádníci DPP / DPČ</span>
            <span class="pill-grp"><span class="mtag hum">člověk</span><span class="mtag id">BRI-10xx</span></span>
          </div>
          <div class="mcard-role">Výpomoc ve skladu e-shopu a pomocné práce osoby poučené</div>
          <div class="mcard-desc">Směny <strong>≥ 3 dny předem</strong>, DPP ≤ 300 h/r (práh pojistného 12 000 Kč/m), DPČ <strong>≤ 1/2 stanovené týd. doby v průměru</strong>, osoba poučená pod dohledem vedoucího elektrotechnika.</div>
        </div>
        <div class="mcard human">
          <div class="mcard-top">
            <span class="mcard-title">SUB · OSVČ &amp; Certified Partner SUB</span>
            <span class="pill-grp"><span class="mtag hum">člověk</span><span class="mtag id">SUB-10xx</span></span>
          </div>
          <div class="mcard-role">Zástupný RT SUB-1007 · Partner SUB · ČKAIT (ORG-UOL zvlášť)</div>
          <div class="mcard-desc">7 pravidel anti-švarcsystému: 10leté Oprávnění TIČR + u RT 5leté Osvědčení + pojistka ≥ 5 mil. Kč; Partner <code>100 % + 10–15 % MRR</code>.</div>
        </div>
        <div class="mcard alert">
          <div class="mcard-top">
            <span class="mcard-title">HARD-STOP BRÁNA (db_hr_lide + JMHZ + DTM)</span>
            <span class="mtag sec">FAIL_CLOSED</span>
          </div>
          <div class="mcard-desc">Nikdo (<code>1002+</code>) nesmí začít práci bez zeleného semaforu: smlouva + <strong>registrace ČSSZ / JMHZ PŘED zahájením práce (od 1. 7. 2026)</strong> + odborná způsobilost + PLS/TIČR + <strong>DTM ČR</strong> + <strong>A1</strong>!</div>
        </div>
      </div>
      <div class="col-foot">100 % JMHZ před nástupem · 0 pokut SÚIP/TIČR · matice zdrojů</div>
    </section>

  </main>

  <!-- 4. BOTTOM 2-BOX STRIP -->
  <footer class="bottom-strip">
    <div class="b-flow">
      <h4>CELOFIREMNÍ TOK HOVORU (ASTERISK + WHISPERX), 360° KARTY „PRACUJ“, ISDS, ELEKTRO WMS, STAVEBNÍHO DENÍKU A MRR (VERZE __VER__)</h4>
      <p><strong>1. Hovor, Omnichannel &amp; Projekce:</strong> Hovor <code>Asterisk</code> (IVR s poučením GDPR, stereo <code>90d</code>/<code>LEGAL_HOLD</code>) + offline <code>WhisperX #t=MM:SS</code> (<code>airgap-spool</code>) + <code>Silero VAD + librosa Kanál L</code> / <code>Stalwart</code> / dělený <code>Chatwoot</code> / ISDS <code>06:50</code> → 3vrstvý CaMeL <code>comm-gateway</code> (webhook &lt; 30 m) → <strong>360° Karta + „Pracuj“ + WebRTC</strong> (<code>14005</code>, ADIS / DTM ČR) → <code>14001</code> <code>QElectroTech .qet/.dxf</code> + Pas rozváděče → Judge <code>15002/15001</code> → <code>mutation_confirm</code>.</p>
      <p><strong>2. Elektro WMS, Zulip, Mapy.cz &amp; Revize:</strong> Rezervace v <strong>Elektro WMS</strong> (schéma <code>wms</code>, <code>VAN-*</code>, <code>S/N</code>, <code>Balíkobot</code>) + téma <code>Zulip</code> (<code>POL-RRRR-NNNNN</code>) + matice zdrojů dle úkolu &amp; <code>Mapy.cz</code> → <strong>Stavební deník</strong> (pečeť <code>pyHanko</code>) + <code>48h šanony</code> + kladná či negativní revize (<code>14003</code>) → osobní <code>QES</code> podpis RT (<code>1001</code> / <code>SUB-1007</code> pod vl. TIČR).</p>
      <p><strong>3. Kniha objektu, ISDOC/EET 2.0, 3úrovňové OCPP &amp; MRR:</strong> Štítek <code>polarita.cz/objekt/&lt;token&gt;</code> + <strong>OCPP</strong> (<code>wss://ocpp.polarita.cz</code>: <code>RO</code> / <code>Reset</code> / <code>UpdateFirmware</code> s <code>mutation_confirm</code>) → faktura ISDOC/Peppol (DB mutex řad vč. <code>ORG-UOL</code>, ADIS, podmíněné <code>EET 2.0</code>) → paušál <strong>MRR</strong> (partner <code>100 % + 10–15 % MRR</code>).</p>
    </div>
    <div class="b-rules">
      <h4>15 ŽELEZNÝCH BEZPEČNOSTNÍCH, KOMUNIKAČNÍCH, PRÁVNÍCH A INŽENÝRSKÝCH POJISTEK FIRMY (VERZE __VER__)</h4>
      <p><strong>1. Decisions (<code>mutation_confirm</code>), ISDS (<code>06:50</code> jen ve službě, jinak <code>&lt; 10d PAUSED</code>) &amp; Break-Glass (<code>SUB-1007</code> pod vl. TIČR + vl. klíč zástupce; YubiKey č. 2 jen pro <code>1001</code>)</strong> · <strong>2. Číselník 2/3/4/5 cifer + <code>ORG-*</code></strong> · <strong>3. OpenBao (raft) + osobní <code>QES</code> (<code>QSCD</code>) vs. pečeť <code>pyHanko</code></strong> · <strong>4. 3vrstvý CaMeL</strong> (<code>sandbox_airgap eth0 none</code> + <code>&lt;untrusted_inbound_comm&gt;</code> + ACL) · <strong>5. <code>cad-urs-engine</code> + <code>metadata-schema-kernel</code> (jen vlastní schémata)</strong> · <strong>6. Worker / Judge &amp; AigisCode</strong> · <strong>7. Hard-Stop <code>db_hr_lide</code>, přednástupní <code>JMHZ</code>, <code>DTM ČR</code> &amp; matice zdrojů</strong> · <strong>8. Anti-švarcsystém (10r Oprávnění / 5r Osvědčení TIČR) &amp; Partner SUB</strong> · <strong>9. Směny ≥ 14d EMP / ≥ 3d BRI, DPČ ≤ 1/2 doby &amp; obecná odpovědnost za vozidla</strong> · <strong>10. Odpovědnost <code>1001</code> za účetnictví + smluvní <code>ORG-UOL</code>, ADIS &amp; DB mutex</strong> · <strong>11. Tvrdý strop __BUDGET_TOTAL__ USD (85 % + 15 % P1, 100 % = stop) &amp; <code>PAUSED</code> ads</strong> · <strong>12. Acyklický Clean Room (bez <code>bytea</code>, 0 PII ve Vaultu), <code>Kanál R FAIL_CLOSED</code> &amp; <code>6+9 PG DB + PgBouncer</code></strong> · <strong>13. 0 titulů u <code>ai</code></strong> · <strong>14. Pas NN dle platné normy, negativní revize &amp; pasy baterií &gt; 2 kWh od 18. 2. 2027</strong> · <strong>15. Stage 1 &amp; 2 Eval 20/20 + týdenní &amp; čtvrtletní Full DR Drill</strong>.</p>
    </div>
  </footer>

</div>
</body>
</html>
"""
    return apply_canon_tokens(template)


ODD_META = [
    ("11-vedeni-a-governance.md", "ÚTVAR 11 · VEDENÍ A GOVERNANCE", "Dvoustupňové vedení firmy (1001 Václav Šercl + 11001 Marek Kovář), Decisions (mutation_confirm), Zulip, Pojistná matice a Break-Glass"),
    ("12-marketing-reklama-a-ai-rust.md", "ODDĚLENÍ 12 · MARKETING, REKLAMA A ai RŮST", "Řízení kampaní na čistou marži POAS (polarita-ads-mcp v PAUSED), Umami, Kalkulačka SVJ, GEO/SEO a atribuce hovorů Asterisk"),
    ("13-eshop-obchod-nakup-a-logistika.md", "ODDĚLENÍ 13 · E-SHOP, ELEKTRO WMS, NÁKUP A LOGISTIKA", "B2C/B2B e-shop polarita.eu, Elektro WMS (VAN-*, bubny, S/N, PHE, pasy baterií pro LMT, EV a průmyslové baterie > 2 kWh od 18. 2. 2027, SCRAP-CU), Balíkobot, RMA (complaint_asserted_at) a 3-Way Match"),
    ("14-elektro-projekce-rozpocty-revize-akademie.md", "ODDĚLENÍ 14 · ELEKTRO, PROJEKCE, ÚRS, REVIZE A AKADEMIE", "QElectroTech + LibreDWG/ezdxf (+ pilot CadCraft), Výrobní pas rozváděče dle platné normy, 9vrstvé rozpočty, kladné i negativní revize, 360° Karta + WebRTC, 3úrovňové OCPP a Akademie"),
    ("15-pravo-legislativa-a-normy-csn.md", "ODDĚLENÍ 15 · PRÁVO, LEGISLATIVA A NORMY ČSN", "Nezávislí Verifikátoři (Worker / Judge): smlouvy, přednástupní JMHZ, obecná odpovědnost za vozidla, pravidla sledování zaměstnanců, zákaz emocí Kanál R, LEGAL_HOLD a normová báze 03-Normy-a-Metodiky/"),
    ("16-finance-fakturace-a-kancelar.md", "ODDĚLENÍ 16 · FINANCE, FAKTURACE, PODATELNA A ÚSTŘEDNA", "ADIS (ručení za DPH), DB mutex, odpovědnost 1001 za účetnictví + smluvní ORG-UOL, MRR ledger, ISDS w9bbdva (06:50 / PAUSED) a Asterisk + WhisperX + Silero VAD + librosa + Stalwart + Chatwoot"),
    ("17-it-vyvoj-bezpecnost-a-ai-platforma.md", "ODDĚLENÍ 17 · IT, VÝVOJ, BEZPEČNOST A ai PLATFORMA", "Server polarita-hq (Ubuntu LTS, Incus/OpenTofu, 6+9 DB PostgreSQL, 0× MySQL/Mongo), 10 modulů, Zulip boti, OpenBao, QES vs. pyHanko a Stage 1/2 Eval Suite"),
    ("18-lide-personalistika-bozp-a-realizace.md", "ODDĚLENÍ 18 · LIDÉ, PERSONALISTIKA, BOZP A REALIZACE", "Živý tým (1002+ EMP / BRI / SUB), Hard-Stop db_hr_lide (0 PII ve Vaultu), přednástupní JMHZ, směny ≥ 14d/3d, matice zdrojů dle úkolu, Mapy.cz a flotila"),
]

AG_META = [
    ("11001-ceo-marek-kovar.md", "11001 · MAREK KOVÁŘ (ai · ceo · 35 USD)", "Výkonný ředitel provozu a hlavní koordinátor 19 ai a živého týmu v Zulip tématech POL-RRRR-NNNNN"),
    ("12001-marketing-tomas-dvorak.md", "12001 · TOMÁŠ DVOŘÁK (ai · marketing · 25 USD)", "Manažer výkonnostní reklamy a kampaní (pásma POAS ≥ 1,8× / 3,0×, stop < 1,5×, polarita-ads-mcp v PAUSED a Umami)"),
    ("12002-obsah-geo-klara-novotna.md", "12002 · KLÁRA NOVOTNÁ (ai · obsah-geo · 20 USD)", "Specialistka obsahu, SEO, GEO (llms.txt), Kalkulačky SVJ a správy recenzí"),
    ("13001-eshop-jakub-cerny.md", "13001 · JAKUB ČERNÝ (ai · eshop · 25 USD)", "Manažer e-shopu polarita.eu, skladu Elektro WMS, expedice a RMA (complaint_asserted_at + LEGAL_HOLD)"),
    ("13002-nakupci-petra-vesela.md", "13002 · PETRA VESELÁ (ai · nakupci · 20 USD)", "Manažerka nákupu, doplňování pojízdných skladů VAN-*, prověrky ADIS (ručení za DPH), 3-Way Match a tendrů NEN"),
    ("14001-projektant-pavel-horak.md", "14001 · PAVEL HORÁK (ai · projektant · 40 USD)", "Specialista elektroprojekce, QElectroTech, Výrobních pasů rozváděčů dle platné normy (CE), DSPS a zámku výkopů DTM ČR"),
    ("14002-rozpoctar-radek-benes.md", "14002 · RADEK BENEŠ (ai · rozpoctar · 30 USD)", "Přípravář a rozpočtář zakázek (9 vrstev CS ÚRS a Změnové listy víceprací #t=MM:SS LEGAL_HOLD)"),
    ("14003-revizak-lukas-kral.md", "14003 · LUKÁŠ KRÁL (ai · revizak · 25 USD)", "Specialista přípravy kladných i negativních revizních zpráv, hlasového Stavebního deníku, 48h šanonů a 3úrovňového OCPP"),
    ("14004-skolitel-martin-pokorny.md", "14004 · MARTIN POKORNÝ (ai · skolitel · 25 USD)", "Koordinátor výuky Elektro Akademie (Moodle LTS, poučení osoby poučené vs. zkoušky elektrotechnika a vedoucího elektrotechnika před 3čl. komisí a Certified Partner SUB)"),
    ("14005-zakazky-lucie-krejcova.md", "14005 · LUCIE KREJČOVÁ (ai · zakazky · 20 USD)", "Koordinátorka 360° Karty spisu „Pracuj“, WebRTC, událostního SLA < 30 min, Silero VAD + librosa Kanál L, Mapy.cz a Lhůtníku"),
    ("15001-pravni-specialista-tereza-jelinkova.md", "15001 · TEREZA JELÍNKOVÁ (ai · pravni-specialista · 30 USD)", "Specialistka smluvní, přednástupního JMHZ, obecné odpovědnosti za vozidla, pravidel sledování zaměstnanců, zákazu emocí Kanál R a GDPR kontroly"),
    ("15002-normovac-zdenek-fiala.md", "15002 · ZDENĚK FIALA (ai · normovac · 30 USD)", "Metodik normové báze 03-Normy-a-Metodiky/ (vč. platné normy pro rozváděče nízkého napětí), 5r Osvědčení / 10r Oprávnění TIČR a metrologie"),
    ("16001-ucetni-eva-kucerova.md", "16001 · EVA KUČEROVÁ (ai · ucetni · 25 USD)", "Finanční kontrolorka, ADIS (ručení za DPH), DB mutexu, 3-Way Match, UOL Read-Only (ORG-UOL) a MRR ledgeru"),
    ("16002-tajemnik-anna-sedlackova.md", "16002 · ANNA SEDLÁČKOVÁ (ai · tajemnik · 15 USD)", "Tajemnice, recepce Asterisk + WhisperX, Stalwart Mail, Chatwoot CE, comm-gateway a Podatelny ISDS (06:50 / PAUSED)"),
    ("17001-programator-ondrej-nemec.md", "17001 · ONDŘEJ NĚMEC (ai · programator · 35 USD)", "Hlavní vývojář 10 vlastních modulů, metadata/registry kernelu a 8cestného routeru comm-gateway"),
    ("17002-webmaster-filip-urban.md", "17002 · FILIP URBAN (ai · webmaster · 15 USD)", "Správce webů, 360° Karty s WebRTC a přehrávačem #t=MM:SS, Kalkulačky SVJ, Chatwoot WebChat a Umami"),
    ("17003-spravce-site-michal-vlcek.md", "17003 · MICHAL VLČEK (ai · spravce-site · 15 USD)", "Správce serveru polarita-hq, Incus/OpenTofu, Asterisk, Zulip, Stalwart, Chatwoot za oauth2-proxy, 6+9 PG DB a DR drillů"),
    ("17004-klicnik-roman-hajek.md", "17004 · ROMAN HÁJEK (ai · klicnik · 10 USD)", "Specialista kyberbezpečnosti, OpenBao, oddělení osobního QES a pečeti pyHanko, Clean Room, 3vrstvého CaMeL a AigisCode"),
    ("17005-ai-provoz-viktor-simek.md", "17005 · VIKTOR ŠIMEK (ai · ai-provoz · 10 USD)", "Specialista Paperclipu, Zulip botů, wt-worker/judge, Stage 1/2 Eval Suite a tvrdého stropu 470 USD (85 % + 15 % P1)"),
    ("18001-personalista-sarka-benesova.md", "18001 · ŠÁRKA BENEŠOVÁ (ai · personalista · 20 USD)", "Manažerka evidence osob v db_hr_lide (0 PII ve Vaultu), přednástupního JMHZ, směn ≥ 14d/3d, BOZP a flotily"),
]


def md_to_html(md_text: str, source_rel: str, included_rels: set[str]) -> str:
    norm_lines = []
    in_fence = False
    for line in md_text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            norm_lines.append(line)
        elif not in_fence:
            norm_lines.append(re.sub(r"^ {2,3}([*-] )", r"    \1", line))
        else:
            norm_lines.append(line)
    raw_html = markdown.markdown(
        "\n".join(norm_lines),
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={"toc": {"slugify": github_slugify}},
    )
    anchor_prefix = f"{doc_slug(source_rel)}--"
    raw_html = re.sub(
        r'(<h[1-6][^>]*\bid=")([^"]+)(")',
        lambda m: f"{m.group(1)}{anchor_prefix}{m.group(2)}{m.group(3)}",
        raw_html,
    )
    return sanitize_html_links(raw_html, source_rel, included_rels)


def build_book_html() -> str:
    included_rels = {
        "README.md",
        "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md",
        "02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md",
        "03-NAVRHY-BALICKU-NA-POZDEJI.md",
        "06-REGISTR-OVERENI-PRAVA-A-NOREM.md",
        "agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md",
    }
    for fname, _, _ in ODD_META:
        included_rels.add(f"oddeleni/{fname}")
    for fname, _, _ in AG_META:
        included_rels.add(f"agenti-a-prompty/{fname}")

    part0_html = md_to_html((ROOT_STRUCT / "README.md").read_text(encoding="utf-8"), "README.md", included_rels)
    part1_html = md_to_html(
        (ROOT_STRUCT / "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md").read_text(encoding="utf-8"),
        "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md",
        included_rels,
    )
    part4_html = md_to_html(
        (ROOT_STRUCT / "02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md").read_text(encoding="utf-8"),
        "02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md",
        included_rels,
    )
    part5_html = md_to_html(
        (ROOT_STRUCT / "03-NAVRHY-BALICKU-NA-POZDEJI.md").read_text(encoding="utf-8"),
        "03-NAVRHY-BALICKU-NA-POZDEJI.md",
        included_rels,
    )

    part2_sections = []
    for fname, eyebrow, title in ODD_META:
        rel = f"oddeleni/{fname}"
        rendered = md_to_html((ODD_DIR / fname).read_text(encoding="utf-8"), rel, included_rels)
        part2_sections.append(f"""
        <section class="chapter-section" id="{doc_slug(rel)}">
          <div class="part-banner">
            <div class="pb-eyebrow">ČÁST II · {eyebrow} · SOUBOR {rel}</div>
            <div class="pb-title">{title}</div>
          </div>
          <div class="md-content">
            {rendered}
          </div>
        </section>
        """)

    core_rel = "agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md"
    part3_sections = [f"""
        <section class="chapter-section" id="{doc_slug(core_rel)}">
          <div class="part-banner">
            <div class="pb-eyebrow">ČÁST III · SPOLEČNÉ JÁDRO PROMPTŮ · {core_rel}</div>
            <div class="pb-title">Pravidla shodná pro všech 20 ai zaměstnanců — jediný zdroj vkládaný do systémových promptů skriptem</div>
          </div>
          <div class="md-content">
            {md_to_html((ROOT_STRUCT / core_rel).read_text(encoding="utf-8"), core_rel, included_rels)}
          </div>
        </section>
        """]
    part6_html = md_to_html(
        (ROOT_STRUCT / "06-REGISTR-OVERENI-PRAVA-A-NOREM.md").read_text(encoding="utf-8"),
        "06-REGISTR-OVERENI-PRAVA-A-NOREM.md",
        included_rels,
    )
    for fname, eyebrow, title in AG_META:
        rel = f"agenti-a-prompty/{fname}"
        rendered = md_to_html((AG_DIR / fname).read_text(encoding="utf-8"), rel, included_rels)
        part3_sections.append(f"""
        <section class="chapter-section" id="{doc_slug(rel)}">
          <div class="part-banner">
            <div class="pb-eyebrow">ČÁST III · KARTA A PROMPTY · {eyebrow} · {rel}</div>
            <div class="pb-title">{title}</div>
          </div>
          <div class="md-content">
            {rendered}
          </div>
        </section>
        """)

    part2_all = "\n".join(part2_sections)
    part3_all = "\n".join(part3_sections)

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<title>Polarita s.r.o. — Kompletní návrh čisté společnosti řízené lidmi (1001+) a 20 ai zaměstnanci · Verze 3.18</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 12mm 12.5mm 13mm 12.5mm;
  }}
  @page :first {{
    margin: 10mm 11mm 10mm 11mm;
  }}
  * {{
    box-sizing: border-box;
  }}
  html, body {{
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    margin: 0;
    padding: 0;
    background: #ffffff;
    color: #1e293b;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.46;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* PAGE 1: DARK NAVY COVER */
  .cover-page {{
    height: 274mm;
    background: linear-gradient(160deg, #0b1c2e 0%, #0d2740 55%, #0c3b59 100%);
    border-radius: 5.2mm;
    padding: 12.5mm 13.5mm 11.0mm 13.5mm;
    color: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    page-break-after: always;
    break-after: page;
    overflow: hidden;
  }}
  .cov-pill {{
    display: inline-block;
    padding: 1.5mm 4.5mm;
    border-radius: 99mm;
    border: 0.35mm solid #0ea5e9;
    background: rgba(14, 165, 233, 0.14);
    color: #7dd3fc;
    font-size: 8.4pt;
    font-weight: 800;
    letter-spacing: 0.06em;
    margin-bottom: 3.4mm;
  }}
  .cov-h1 {{
    font-size: 30.0pt;
    font-weight: 900;
    letter-spacing: -0.02em;
    margin: 0 0 2.2mm 0;
    line-height: 1.08;
    color: #ffffff;
  }}
  .cov-sub {{
    font-size: 12.4pt;
    font-weight: 600;
    color: #bae6fd;
    margin: 0 0 3.8mm 0;
    line-height: 1.28;
  }}
  .cov-lead {{
    font-size: 8.7pt;
    line-height: 1.5;
    color: #cbd5e1;
    margin: 0;
  }}
  .cov-lead code {{
    background: rgba(255, 255, 255, 0.11);
    color: #f8fafc;
    border: 0.25mm solid rgba(148, 163, 184, 0.35);
    padding: 0.12mm 1.1mm;
    border-radius: 1.1mm;
    font-size: 8.1pt;
    font-family: Consolas, "Cascadia Mono", monospace;
  }}
  .cov-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3.4mm;
    margin: 3.6mm 0;
  }}
  .cov-stat {{
    background: rgba(255, 255, 255, 0.055);
    border: 0.3mm solid rgba(148, 163, 184, 0.28);
    border-radius: 3.2mm;
    padding: 3.4mm 4.4mm;
  }}
  .cov-stat .num {{
    font-size: 15.5pt;
    font-weight: 900;
    color: #38bdf8;
    margin-bottom: 0.8mm;
    line-height: 1.15;
  }}
  .cov-stat .txt {{
    font-size: 8.5pt;
    color: #cbd5e1;
    line-height: 1.34;
  }}
  .cov-meta {{
    border-top: 0.3mm solid rgba(148, 163, 184, 0.28);
    padding-top: 3.2mm;
    font-size: 8.2pt;
    line-height: 1.48;
    color: #cbd5e1;
  }}
  .cov-meta strong {{ color: #ffffff; }}
  .cov-meta code {{
    background: rgba(255, 255, 255, 0.11);
    color: #f8fafc;
    border: none;
    padding: 0.12mm 1.1mm;
    border-radius: 1mm;
    font-size: 7.9pt;
    font-family: Consolas, monospace;
  }}

  /* OVERVIEW & REGISTRY PAGES */
  .overview-page {{
    page-break-after: always;
    break-after: page;
    max-width: 100%;
  }}
  .chapter-section {{
    page-break-before: always;
    break-before: page;
    max-width: 100%;
  }}
  .part-banner {{
    background: linear-gradient(135deg, #0b1c2e 0%, #102e4a 100%);
    border-left: 2.2mm solid #0ea5e9;
    border-radius: 3.0mm;
    padding: 4.6mm 6.0mm;
    color: #ffffff;
    margin-bottom: 4.4mm;
    break-inside: avoid;
  }}
  .pb-eyebrow {{
    font-size: 8.0pt;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: #38bdf8;
    margin-bottom: 1.2mm;
    overflow-wrap: anywhere;
  }}
  .pb-title {{
    font-size: 13.0pt;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.22;
  }}

  /* MARKDOWN CONTENT STYLING — ZERO HORIZONTAL OVERFLOW (F33 FIX) */
  .md-content {{
    max-width: 100%;
    overflow-wrap: anywhere;
    word-break: break-word;
  }}
  .md-content h1, .overview-page h1 {{
    font-size: 13.6pt;
    font-weight: 800;
    color: #0b1f33;
    border-bottom: 0.55mm solid #0284c7;
    padding-bottom: 1.5mm;
    margin: 2.2mm 0 2.6mm 0;
    line-height: 1.24;
    break-after: avoid;
  }}
  .md-content h2, .overview-page h2 {{
    font-size: 11.0pt;
    font-weight: 800;
    color: #0c4a6e;
    margin: 3.8mm 0 1.7mm 0;
    line-height: 1.28;
    break-after: avoid;
  }}
  .md-content h3 {{
    font-size: 9.8pt;
    font-weight: 800;
    color: #0f172a;
    margin: 3.2mm 0 1.3mm 0;
    break-after: avoid;
  }}
  .md-content p, .overview-page p {{ margin: 0 0 2.0mm 0; }}
  .md-content ul, .md-content ol {{ margin: 0 0 2.5mm 0; padding-left: 5.2mm; }}
  .md-content li {{ margin-bottom: 0.95mm; }}
  .md-content hr {{ border: none; border-top: 0.3mm solid #e2e8f0; margin: 3.4mm 0; }}
  .md-content a {{ color: #0369a1; text-decoration: underline; font-weight: 600; overflow-wrap: anywhere; }}
  .local-ref {{
    color: #0f172a;
    font-weight: 600;
    background: #f1f5f9;
    border-bottom: 0.25mm dashed #64748b;
    padding: 0 0.7mm;
    border-radius: 0.7mm;
    overflow-wrap: anywhere;
  }}

  code {{
    font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
    font-size: 8.3pt;
    background: #f1f5f9;
    color: #0f172a;
    border: 0.24mm solid #cbd5e1;
    border-radius: 1.0mm;
    padding: 0.1mm 0.95mm;
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
  }}
  th code {{
    background: rgba(255, 255, 255, 0.14);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.32);
  }}
  pre {{
    max-width: 100%;
    background: #f8fafc;
    border: 0.3mm solid #cbd5e1;
    border-left: 1.2mm solid #0284c7;
    border-radius: 1.8mm;
    padding: 2.8mm 3.4mm;
    margin: 2.2mm 0 3.4mm 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    word-break: break-word;
    font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
    font-size: 8.1pt;
    line-height: 1.38;
    color: #0f172a;
  }}
  pre code {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: inherit;
    color: inherit;
    white-space: pre-wrap;
  }}
  blockquote {{
    margin: 2.4mm 0;
    padding: 2.2mm 3.6mm;
    background: #f0f9ff;
    border-left: 1.2mm solid #0284c7;
    border-radius: 1.4mm;
    color: #0c4a6e;
    font-size: 8.9pt;
  }}

  table {{
    width: 100%;
    max-width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
    margin: 2.0mm 0 3.2mm 0;
    font-size: 8.3pt;
    line-height: 1.33;
  }}
  thead {{ display: table-header-group; }}
  th {{
    background: #0b1f33;
    color: #ffffff;
    font-weight: 700;
    text-align: left;
    padding: 1.6mm 1.9mm;
    border: 0.25mm solid #0b1f33;
    overflow-wrap: anywhere;
    word-break: break-word;
  }}
  td {{
    padding: 1.5mm 1.9mm;
    border: 0.25mm solid #cbd5e1;
    vertical-align: top;
    overflow-wrap: anywhere;
    word-break: break-word;
  }}
  tbody tr:nth-child(even) {{ background: #f8fafc; }}
  tr {{ break-inside: avoid; }}

  table.reg-table {{
    font-size: 7.9pt;
    line-height: 1.25;
  }}
  table.reg-table th {{ padding: 1.35mm 1.4mm; }}
  table.reg-table td {{ padding: 1.15mm 1.4mm; }}
  table.reg-table code {{ font-size: 7.5pt; padding: 0.06mm 0.7mm; }}
</style>
</head>
<body>

  <!-- PAGE 1: DARK NAVY COVER -->
  <div class="cover-page">
    <div>
      <div class="cov-pill">GREENFIELD HYBRID ai-first BLUEPRINT · VERZE {VER} · JÁDRO PO AUDITU + BALÍČKY S1–S7 · 2026</div>
      <h1 class="cov-h1">POLARITA S.R.O.</h1>
      <div class="cov-sub">Kompletní návrh čisté společnosti řízené lidmi (1001+) a 20 ai zaměstnanci (11001–18001) · Verze {VER}</div>
      <p class="cov-lead">
        Architektura od nuly · Server Ubuntu LTS (<code>polarita-hq</code> · <code>Incus + OpenTofu</code> · <code>6+9 DB PostgreSQL</code> · <code>0× MySQL</code> · <code>0× MongoDB</code>) ·
        Útvar <code>11</code> + 7 oddělení (<code>12–18</code>) · Živý tým fyzických osob <code>1001–9999</code> (<code>STAT / EMP / BRI / SUB</code>), registr dodavatelských firem <code>ORG-*</code> (<code>ORG-UOL</code>) a síť <code>Certified Partner SUB</code> (<code>100 % + 10–15 % MRR</code>) ·
        Softwarová ústředna <code>Asterisk</code> (<code>WebRTC + Linphone</code>, <code>0</code> veř. SIP portů, stereo <code>90d</code> vs. <code>LEGAL_HOLD 3–10 let</code>), lokální přepis <code>WhisperX</code> (<code>#t=MM:SS</code>),
        komerčně neomezená urgence <code>Silero VAD + librosa</code> (<code>MIT / ISC</code>) výhradně nad <code>Kanálem L</code> (<code>Kanál R = FAIL_CLOSED</code> dle předpisů EU o ai &amp; pravidel pro sledování zaměstnanců), týmový hub <code>Zulip</code> (<code>Blok 7</code>),
        pošta <code>Stalwart Mail</code>, omnichannel <code>Chatwoot CE</code> (veřejně jen widget a webhooky kanálů, ostatní včetně <code>Platform API</code> za VPN + <code>oauth2-proxy</code>) a 8cestný router <code>comm-gateway</code> (3vrstvý <code>CaMeL</code>) ·
        Podatelna ISDS <code>{COMPANY['isds']}</code> (<code>06:50</code> jen při aktivní službě, jinak <code>PAUSED</code>, testy na <code>czebox.cz</code>) · přednástupní registrace ČSSZ / <code>JMHZ</code> ·
        platná norma pro rozváděče nízkého napětí, kladné i negativní revize, <code>QElectroTech</code> (+ pilot <code>CadCraft</code>), <code>Elektro WMS</code>, <code>Mapy.cz</code>, 3úrovňové <code>OCPP</code>, <code>Stage 1 &amp; 2 Eval Suite</code> a <strong>Master Playbook (Týdny 0–12)</strong>
      </p>
    </div>

    <div class="cov-grid">
      <div class="cov-stat">
        <div class="num">1001+ &amp; 20 ai</div>
        <div class="txt">Jednatel (1001) + živý tým + smluvní ORG-UOL + 20 ai botů v Zulip</div>
      </div>
      <div class="cov-stat">
        <div class="num">Verze {VER} · S1–S7</div>
        <div class="txt">Acyklické Bloky 0–12 (Týdny 0–12), navazující Bloky 13–19 (balíčky S1–S7) a Eval Suite 20 + 137 scénářů</div>
      </div>
      <div class="cov-stat">
        <div class="num">6+9 DB PG · 0× MySQL</div>
        <div class="txt">6 doménových + 9 servisních DB PostgreSQL (Clean Room, 0 PII ve Vaultu) + čtvrtletní Full DR</div>
      </div>
      <div class="cov-stat">
        <div class="num">{BUDGET_TOTAL} USD (85 % + 15 %)</div>
        <div class="txt">Tvrdý globální strop ai tokenů (85 % provoz + 15 % P1 rezerva, 100 % = tvrdý stop)</div>
      </div>
    </div>

    <div class="cov-meta">
      <div><strong>Subjekt:</strong> Polarita s.r.o. · IČO: {COMPANY['ico']} · DIČ: {COMPANY['dic']} · Sp. zn. C 361683 (MS v Praze) · ISDS: <code>{COMPANY['isds']}</code> (Podatelna <code>16002</code>)</div>
      <div><strong>Sídlo a výchozí pobočka:</strong> Pobočka <code>101</code> (<code>{COMPANY['branch']}</code> Praha — Centrála), Na Folimance 2155/15, 120 00 Praha 2</div>
      <div><strong>Jednatel a odborný garant elektro:</strong> Václav Šercl (os. č. <code>1001</code> · <code>STAT-1001</code> · 10leté Oprávnění TIČR + 5leté Osvědčení RT · osobní <code>QES</code> na <code>QSCD</code>)</div>
      <div><strong>Číselná soustava:</strong> 2c Útvar (<code>11–99</code>) · 3c Pobočka (<code>101–999</code>) · 4c Člověk (<code>1001–9999</code>) · <code>ORG-*</code> Dodavatelská firma · 5c ai (<code>11001–99999</code>)</div>
      <div><strong>Obsah knihy (Verze {VER}):</strong> Část 0 — Návod po blocích 0–12 · Část I — Hlavní plán + Master Playbook · Část II — Charty útvarů (11–18) · Část III — Společné jádro + 20 ai zaměstnanců · Část IV — Metodika rozšiřování · Část V — Balíčky S1–S7 · Část VI — Právní a normová báze</div>
    </div>
  </div>

  <!-- PAGE 2: DOCUMENT STRUCTURE OVERVIEW -->
  <div class="overview-page">
    <h1>Přehled struktury dokumentu (Modrá kniha Polarita s.r.o. · Verze {VER})</h1>
    <p>
      Tento souborný dokument sjednocuje kompletní zakládací návrh hybridní digitální a realizační společnosti <strong>Polarita s.r.o.</strong>
      ve <strong>Verzi {VER}</strong> (jádro po nezávislém auditu a zapracované rozvojové balíčky <code>S1–S7</code> jako <code>Bloky 13–19</code>): acyklický postup výstavby <code>Bloků 0–12</code> (<code>Týden 0 → Týdny 11–12</code>),
      ochranu doručovacích účinků ISDS (<code>PAUSED</code> při neobsazené nepřítomnosti &lt; 10 dnů, testy na <code>czebox.cz</code>), přednástupní registraci ČSSZ / <code>JMHZ</code>,
      platnou normu pro rozváděče nízkého napětí, podporu negativní revizní zprávy, 100% open-source akustickou urgenci <code>Silero VAD + librosa</code> a čistou přenositelnou sazbu 1:1.
    </p>

    <table>
      <thead>
        <tr>
          <th style="width: 18%;">Část knihy</th>
          <th style="width: 28%;">Kapitoly ve složce <code>firemni-struktura/</code></th>
          <th style="width: 54%;">Co zde najdete (Verze {VER})</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>ČÁST 0</strong><br>Výchozí bod &amp; Bloky 0–12</td>
          <td><a href="#{doc_slug('README.md')}">README.md</a></td>
          <td>Hlavní rozcestník systému, <strong>provozní protokol realizačního <code>ai</code> agenta (<code>kap. 0</code> — subagenti, oponentura jinou <code>ai</code> a předání <code>11001 ceo</code>)</strong>, číselná soustava (<code>2/3/4/5</code> + <code>ORG-*</code>), <strong>návod po blocích (<code>Blok 0–12</code> · <code>Týdny 0–12</code> · <code>Eval 20/20</code>)</strong> a katalog všech 50 dokumentů.</td>
        </tr>
        <tr>
          <td><strong>ČÁST I</strong><br>Hlavní plán &amp; Master Playbook</td>
          <td><a href="#{doc_slug('00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md')}">00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md</a></td>
          <td>Statutární identifikace, odpovědnost účetní jednotky (+ smluvní <code>ORG-UOL</code>), <code>Asterisk + WhisperX + Silero VAD + librosa + Zulip + Stalwart + Chatwoot CE</code>, <code>Elektro WMS</code>, matice zdrojů dle úkolu + <code>Mapy.cz</code>, přednástupní <code>JMHZ</code>, platná norma pro rozváděče nízkého napětí, <code>360° Karta + „Pracuj“</code>, hypotézy pilotu a <strong>Master Playbook (Týdny 0–12)</strong>.</td>
        </tr>
        <tr>
          <td><strong>ČÁST II</strong><br>Charty Útvaru 11 a 7 oddělení (12–18)</td>
          <td><code>oddeleni/11-vedeni-a-governance.md</code> až <code>oddeleni/18-lide-personalistika-bozp-a-realizace.md</code></td>
          <td>Detailní charty Vedení (<code>11</code>), Marketingu (<code>12</code> — pásma POAS), Obchodu a WMS (<code>13</code> — RMA <code>complaint_asserted_at</code>, baterie &gt; 2 kWh od 18. 2. 2027), Inženýringu a Akademie (<code>14</code> — <code>QElectroTech</code>, negativní revize, poučení vs. zkoušky před 3čl. komisí), Práva a Norem (<code>15</code> — odpovědnost za vozidla, registr norem), Financí a Kanceláře (<code>16</code> — ISDS <code>PAUSED</code>, mzdy 2.–3. den), IT (<code>17</code>) a Lidí (<code>18</code> — směny ≥ 14d/3d, DPČ ≤ 1/2 doby, 0 PII ve Vaultu).</td>
        </tr>
        <tr>
          <td><strong>ČÁST III</strong><br>Jádro &amp; karty 20 ai zaměstnanců</td>
          <td><a href="#{doc_slug('agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md')}">00-SPOLECNE-JADRO-PROMPTU.md</a> a <code>11001</code> až <code>18001</code></td>
          <td>Společné jádro pravidel (jediný zdroj) a atomická karta každého z 20 ai zaměstnanců se <strong>100% sjednocenými omezeními přímo v kopírovatelném <code>System Promptu</code></strong>, stropy v rámci <code>{BUDGET_TOTAL} USD</code> (85 % provoz + 15 % P1 rezerva) a provozními prompty Verze {VER}.</td>
        </tr>
        <tr>
          <td><strong>ČÁST IV</strong><br>Metodika rozšiřování firmy</td>
          <td><a href="#{doc_slug('02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md')}">02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md</a></td>
          <td>Krokové návody pro: <strong>1) Novou pobočku</strong> (kanonický <code>case_id POL-RRRR-NNNNN</code> + <code>branch_id</code>, samostatná entita <code>Z3</code> podmíněná architektonickým balíčkem <code>legal_entity_id</code>), <strong>2) Nové oddělení (<code>19+</code>)</strong>, <strong>3) Nového ai zaměstnance</strong> a <strong>4) Nástup člověka</strong> (registrace ČSSZ <strong>před zahájením práce</strong>).</td>
        </tr>
        <tr>
          <td><strong>ČÁST V</strong><br>Registr balíčků S1–S7 (Bloky 13–19)</td>
          <td><a href="#{doc_slug('03-NAVRHY-BALICKU-NA-POZDEJI.md')}">03-NAVRHY-BALICKU-NA-POZDEJI.md</a></td>
          <td>Registr zapracovaných balíčků <code>S1–S7</code>: stav zapracování, zbývající práce a odkazy na řídicí dokumenty ve složce <code>balicky/</code>. Rozcestník a řídicí dokumenty <code>Bloků 13–19</code> jsou vysázeny v knize <code>04</code> (Část III).</td>
        </tr>
        <tr>
          <td><strong>ČÁST VI</strong><br>Právní a normová báze</td>
          <td><a href="#{doc_slug('06-REGISTR-OVERENI-PRAVA-A-NOREM.md')}">06-REGISTR-OVERENI-PRAVA-A-NOREM.md</a></td>
          <td>Zásada, že návod neobsahuje čísla předpisů ani označení norem: předpisy, normy a smlouvy se načítají z úředních zdrojů až po nasazení, pravidelně se hlídají a aktualizují. Postup při jejich změně, ověřené technické údaje a rozhodnutí čekající na jednatele <code>1001</code>.</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- PAGE 3: QUICK ATOMIC REGISTRY OF PEOPLE (1001+), ORG-* & 20 ai (11001-18001) -->
  <div class="overview-page">
    <h1>Rychlý atomický rejstřík osob (1001+), dodavatelských organizací (ORG-*) a 20 ai (11001–18001)</h1>
    <table class="reg-table">
      <thead>
        <tr>
          <th style="width: 8%;">Číslo / Kód</th>
          <th style="width: 11%;">Útvar</th>
          <th style="width: 8%;">Typ</th>
          <th style="width: 8.5%;">Jméno</th>
          <th style="width: 10%;">Příjmení / Název</th>
          <th style="width: 13%;">Systémové ID</th>
          <th style="width: 33.5%;">Pracovní pozice / Smluvní role (Verze {VER})</th>
          <th style="width: 8%;">Strop</th>
        </tr>
      </thead>
      <tbody>
        <tr><td><code>1001</code></td><td>11 Vedení</td><td><code>člověk</code></td><td><strong>Václav</strong></td><td><strong>Šercl</strong></td><td><code>STAT-1001</code></td><td>Vlastník, jednatel a garant elektro (10r Oprávnění + 5r Osvědčení TIČR)</td><td>SoVF</td></tr>
        <tr><td><code>1002+</code></td><td>18 Lidé</td><td><code>člověk</code></td><td><em>Živý tým</em></td><td><em>Fyzické osoby</em></td><td><code>EMP/BRI/SUB</code></td><td>Montéři (elektrotechnik / vedoucí elektrotechnik), sklad (os. poučená), zástupný RT <code>SUB-1007</code>, komise, ČKAIT, Partner SUB</td><td>dle sml.</td></tr>
        <tr><td><code>ORG-UOL</code></td><td>16 Externí</td><td><code>organizace</code></td><td><em>Smluvní</em></td><td><strong>UOL Účetnictví</strong></td><td><code>ORG-UOL</code></td><td>Smluvní účetní a mzdový zpracovatel / daňový zmocněnec (mimo 4místná ID osob!)</td><td>B2B</td></tr>
        <tr><td><code>11001</code></td><td>11 Vedení</td><td><code>ai</code></td><td><strong>Marek</strong></td><td><strong>Kovář</strong></td><td><code>ceo</code></td><td>Výkonný ředitel provozu a koordinátor (Zulip témata, matice zdrojů, Decisions)</td><td>35 USD</td></tr>
        <tr><td><code>12001</code></td><td>12 Marketing</td><td><code>ai</code></td><td><strong>Tomáš</strong></td><td><strong>Dvořák</strong></td><td><code>marketing</code></td><td>Manažer výkonnostní reklamy (pásma POAS, polarita-ads-mcp v PAUSED)</td><td>25 USD</td></tr>
        <tr><td><code>12002</code></td><td>12 Marketing</td><td><code>ai</code></td><td><strong>Klára</strong></td><td><strong>Novotná</strong></td><td><code>obsah-geo</code></td><td>Specialistka obsahu, SEO, GEO, Kalkulačky SVJ a recenzí</td><td>20 USD</td></tr>
        <tr><td><code>13001</code></td><td>13 Obchod</td><td><code>ai</code></td><td><strong>Jakub</strong></td><td><strong>Černý</strong></td><td><code>eshop</code></td><td>Manažer polarita.eu, Elektro WMS, pasů baterií pro LMT, EV a průmyslové baterie &gt; 2 kWh a RMA (complaint_asserted_at)</td><td>25 USD</td></tr>
        <tr><td><code>13002</code></td><td>13 Obchod</td><td><code>ai</code></td><td><strong>Petra</strong></td><td><strong>Veselá</strong></td><td><code>nakupci</code></td><td>Manažerka nákupu, VAN-*, prověrky ADIS (ručení za DPH), 3-Way Match a tendrů NEN</td><td>20 USD</td></tr>
        <tr><td><code>14001</code></td><td>14 Inženýring</td><td><code>ai</code></td><td><strong>Pavel</strong></td><td><strong>Horák</strong></td><td><code>projektant</code></td><td>Specialista elektroprojekce, QElectroTech, pasů rozváděčů dle platné normy a DTM ČR</td><td>40 USD</td></tr>
        <tr><td><code>14002</code></td><td>14 Inženýring</td><td><code>ai</code></td><td><strong>Radek</strong></td><td><strong>Beneš</strong></td><td><code>rozpoctar</code></td><td>Přípravář a rozpočtář zakázek (9 vrstev CS ÚRS a vícepráce #t=MM:SS)</td><td>30 USD</td></tr>
        <tr><td><code>14003</code></td><td>14 Inženýring</td><td><code>ai</code></td><td><strong>Lukáš</strong></td><td><strong>Král</strong></td><td><code>revizak</code></td><td>Příprava kladných i negativních revizí, stavebního deníku, 48h šanonů a 3úrovňového OCPP</td><td>25 USD</td></tr>
        <tr><td><code>14004</code></td><td>14 Akademie</td><td><code>ai</code></td><td><strong>Martin</strong></td><td><strong>Pokorný</strong></td><td><code>skolitel</code></td><td>Koordinátor Elektro Akademie (Moodle LTS, poučení vs. zkoušky před 3čl. komisí, Partner SUB)</td><td>25 USD</td></tr>
        <tr><td><code>14005</code></td><td>14 Inženýring</td><td><code>ai</code></td><td><strong>Lucie</strong></td><td><strong>Krejčová</strong></td><td><code>zakazky</code></td><td>360° Karta „Pracuj“, WebRTC, SLA &lt; 30 m, Silero VAD + librosa Kanál L, Mapy.cz</td><td>20 USD</td></tr>
        <tr><td><code>15001</code></td><td>15 Verifikace</td><td><code>ai</code></td><td><strong>Tereza</strong></td><td><strong>Jelínková</strong></td><td><code>pravni-specialista</code></td><td>Smlouvy, přednástupní JMHZ, odpovědnost za vozidla, pravidla sledování, Kanál R FAIL_CLOSED</td><td>30 USD</td></tr>
        <tr><td><code>15002</code></td><td>15 Verifikace</td><td><code>ai</code></td><td><strong>Zdeněk</strong></td><td><strong>Fiala</strong></td><td><code>normovac</code></td><td>Metodik normové báze 03-Normy-a-Metodiky/ (vč. rozváděčů NN), 5r/10r TIČR a metrologie</td><td>30 USD</td></tr>
        <tr><td><code>16001</code></td><td>16 Finance</td><td><code>ai</code></td><td><strong>Eva</strong></td><td><strong>Kučerová</strong></td><td><code>ucetni</code></td><td>Finanční kontrolorka, ADIS, 3-Way Match, ORG-UOL (mzdy 2.–3. den) a MRR</td><td>25 USD</td></tr>
        <tr><td><code>16002</code></td><td>16 Kancelář</td><td><code>ai</code></td><td><strong>Anna</strong></td><td><strong>Sedláčková</strong></td><td><code>tajemnik</code></td><td>Recepce Asterisk + WhisperX, Stalwart, Chatwoot a ISDS w9bbdva (06:50 / PAUSED)</td><td>15 USD</td></tr>
        <tr><td><code>17001</code></td><td>17 IT &amp; ai</td><td><code>ai</code></td><td><strong>Ondřej</strong></td><td><strong>Němec</strong></td><td><code>programator</code></td><td>Hlavní vývojář 10 modulů (metadata-schema-kernel jen vlastní schémata, comm-gateway)</td><td>35 USD</td></tr>
        <tr><td><code>17002</code></td><td>17 IT &amp; ai</td><td><code>ai</code></td><td><strong>Filip</strong></td><td><strong>Urban</strong></td><td><code>webmaster</code></td><td>Správce webů, 360° Karty + WebRTC, Kalkulačky SVJ, Umami a UX</td><td>15 USD</td></tr>
        <tr><td><code>17003</code></td><td>17 IT &amp; ai</td><td><code>ai</code></td><td><strong>Michal</strong></td><td><strong>Vlček</strong></td><td><code>spravce-site</code></td><td>Správce Ubuntu LTS, Incus/OpenTofu, Zulip, Chatwoot oauth2-proxy, 6+9 DB a DR</td><td>15 USD</td></tr>
        <tr><td><code>17004</code></td><td>17 IT &amp; ai</td><td><code>ai</code></td><td><strong>Roman</strong></td><td><strong>Hájek</strong></td><td><code>klicnik</code></td><td>Kyberbezpečnost, OpenBao, QES vs. pyHanko, Clean Room, 3vrstvý CaMeL a AigisCode</td><td>10 USD</td></tr>
        <tr><td><code>17005</code></td><td>17 IT &amp; ai</td><td><code>ai</code></td><td><strong>Viktor</strong></td><td><strong>Šimek</strong></td><td><code>ai-provoz</code></td><td>Paperclip, Zulip boti, wt-worker/judge, Stage 1/2 Eval a strop {BUDGET_TOTAL} USD (85+15 %)</td><td>10 USD</td></tr>
        <tr><td><code>18001</code></td><td>18 Lidé &amp; BOZP</td><td><code>ai</code></td><td><strong>Šárka</strong></td><td><strong>Benešová</strong></td><td><code>personalista</code></td><td>Evidence osob v db_hr_lide (0 PII ve Vaultu), přednástupní JMHZ, směny ≥ 14d/3d</td><td>20 USD</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ČÁST 0: README COMMISSIONING BLOCKS 0-12 -->
  <section class="chapter-section" id="{doc_slug('README.md')}">
    <div class="part-banner">
      <div class="pb-eyebrow">ČÁST 0 · VÝCHOZÍ BOD · SOUBOR README.md</div>
      <div class="pb-title">Výchozí rozcestník a acyklický návod ke zprovoznění celého systému po blocích (Blok 0 až Blok 12 · Týden 0 → Týdny 11–12 · Go-Live Gate 12/12 PASS) a navazující Bloky 13–19 (S1–S7)</div>
    </div>
    <div class="md-content">
      {part0_html}
    </div>
  </section>

  <!-- ČÁST I: MASTER BLUEPRINT -->
  <section class="chapter-section" id="{doc_slug('00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md')}">
    <div class="part-banner">
      <div class="pb-eyebrow">ČÁST I · SOUBOR 00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md</div>
      <div class="pb-title">Hlavní zakladatelský plán společnosti Polarita s.r.o., komunikační architektura K1–K5, Master Playbook (Bloky 0–12 · Týden 0 → Týdny 11–12) a 15 železných pravidel</div>
    </div>
    <div class="md-content">
      {part1_html}
    </div>
  </section>

  <!-- ČÁST II: 8 DEPARTMENTS -->
  {part2_all}

  <!-- ČÁST III: 20 ai AGENTS -->
  {part3_all}

  <!-- ČÁST IV: EXPANSION METHODOLOGY -->
  <section class="chapter-section" id="{doc_slug('02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md')}">
    <div class="part-banner">
      <div class="pb-eyebrow">ČÁST IV · SOUBOR 02-METODIKA-ROZSIROVANI-FIRMY-POBOCKY-ODDELENI-AI-LIDE.md</div>
      <div class="pb-title">Metodika rozšiřování společnosti — nová pobočka (102+, kanonický case_id, podmínka Z3), nové oddělení (19+), nový ai zaměstnanec (ÚÚPPP) a živý člověk (1002+)</div>
    </div>
    <div class="md-content">
      {part4_html}
    </div>
  </section>

  <!-- ČÁST V: DEFERRED PACKAGES S1-S7 -->
  <section class="chapter-section" id="{doc_slug('03-NAVRHY-BALICKU-NA-POZDEJI.md')}">
    <div class="part-banner">
      <div class="pb-eyebrow">ČÁST V · SOUBOR 03-NAVRHY-BALICKU-NA-POZDEJI.md</div>
      <div class="pb-title">Registr rozvojových balíčků S1 – S7 (Bloky 13–19 Rozvojové Etapy II a Strategické Etapy III)</div>
    </div>
    <div class="md-content">
      {part5_html}
    </div>
  </section>

  <!-- ČÁST VI: VERIFICATION REGISTER -->
  <section class="chapter-section" id="{doc_slug('06-REGISTR-OVERENI-PRAVA-A-NOREM.md')}">
    <div class="part-banner">
      <div class="pb-eyebrow">ČÁST VI · SOUBOR 06-REGISTR-OVERENI-PRAVA-A-NOREM.md</div>
      <div class="pb-title">Právní a normová báze: pravidla pro předpisy, normy a smlouvy po nasazení a registr otevřených bodů</div>
    </div>
    <div class="md-content">
      {part6_html}
    </div>
  </section>

</body>
</html>
"""


def render_pdf(browser: Path, html_path: Path, pdf_path: Path) -> None:
    file_url = html_path.resolve().as_uri()
    with tempfile.TemporaryDirectory() as out_tmp:
        tmp_pdf = Path(out_tmp) / pdf_path.name
        cmd = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={tmp_pdf}",
            file_url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode != 0 or not tmp_pdf.is_file() or tmp_pdf.stat().st_size == 0:
            raise RuntimeError(f"Chyba při tisku {pdf_path.name}: {res.stderr}")
        shutil.move(str(tmp_pdf), str(pdf_path))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    browser = find_browser()
    print(f"Použitý prohlížeč: {browser}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        scratch = Path(tmp_dir)
        poster_html = scratch / "poster_org_a3.html"
        book_html = scratch / "book_org_a4.html"
        poster_html.write_text(build_poster_html(), encoding="utf-8")
        book_html.write_text(build_book_html(), encoding="utf-8")
        print(f"HTML předlohy organizace Verze {VER} vygenerovány v dočasné složce.")

        render_pdf(browser, poster_html, OUT_POSTER_PDF)
        print(f"Vytvořeno A3 PDF: {OUT_POSTER_PDF} ({OUT_POSTER_PDF.stat().st_size:,} B)")

        render_pdf(browser, book_html, OUT_BOOK_PDF)
        print(f"Vytvořeno A4 PDF: {OUT_BOOK_PDF} ({OUT_BOOK_PDF.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
