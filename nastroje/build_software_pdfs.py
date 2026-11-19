# -*- coding: utf-8 -*-
"""
Generátor tiskových PDF výstupů softwarové architektury Polarita s.r.o. (Verze 2.7):
  1) 05-SOFTWAROVA-MAPA-A3-2026.pdf (1 strana A3 na šířku 420×297 mm, čitelná sazba bez zmenšení)
  2) 04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf (souborná Modrá kniha A4, 0× file:// URI, 1:1 měřítko)
Cesty jsou relativní k umístění skriptu (nastroje/ ve složce firemni-struktura/); HTML předlohy vznikají
v dočasné složce systému a do firemni-struktura/ se zapisují výhradně výsledná PDF.
Kniha 04 obsahuje i Část III — řídicí dokumenty rozvojových balíčků S1–S7 (Bloky 13–19) ze složky balicky/.
Spuštění: python nastroje/build_software_pdfs.py   (vyžaduje balík markdown a Chrome nebo Edge)
Striktně bez čísel verzí u softwaru, protokolů a licencí!
"""

import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote
import markdown

ROOT_STRUCT = Path(__file__).resolve().parents[1]
SW_DIR = ROOT_STRUCT / "software"
SCRATCH_DIR = Path(tempfile.gettempdir()) / "polarita-pdf-build"

OUT_BOOK_PDF = ROOT_STRUCT / "04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf"
OUT_POSTER_PDF = ROOT_STRUCT / "05-SOFTWAROVA-MAPA-A3-2026.pdf"

POSTER_HTML_PATH = SCRATCH_DIR / "poster_software_a3.html"
BOOK_HTML_PATH = SCRATCH_DIR / "book_software_a4.html"

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


def sanitize_html_links(html: str, source_rel: str, included_rels: set[str]) -> str:
    """
    F32 fix: Převede odkazy uvnitř knihy na interní #doc-... kotvy a odkazy mimo knihu na <span class="local-ref">,
    aby nevznikla ani jedna file:// URI anotace.
    """
    src_dir = (ROOT_STRUCT / source_rel).parent.resolve()
    root_res = ROOT_STRUCT.resolve()

    def repl(match: re.Match) -> str:
        href = match.group(1).strip()
        inner = match.group(2)
        if href.startswith(("https://", "http://", "mailto:", "#")):
            return match.group(0)
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


def build_poster_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<title>Polarita s.r.o. — Softwarová a serverová architektura · Verze 2.7 (A3)</title>
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
    font-size: 6.7pt;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    overflow: hidden;
  }
  code {
    font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
    font-size: 6.25pt;
    background: #f1f5f9;
    color: #0f172a;
    border: 0.2mm solid #cbd5e1;
    border-radius: 0.85mm;
    padding: 0.04mm 0.7mm;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .canvas {
    width: 420mm;
    height: 297mm;
    padding: 3.8mm 4.8mm 3.8mm 4.8mm;
    display: flex;
    flex-direction: column;
    gap: 1.75mm;
    background: #f8fafc;
    overflow: hidden;
  }

  /* 1. TOP DARK HEADER */
  .topbar {
    background: linear-gradient(100deg, #091929 0%, #0d2e47 58%, #0f445e 100%);
    color: #ffffff;
    border-radius: 2.4mm;
    padding: 2.15mm 4.0mm;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 3.8mm;
    flex-shrink: 0;
  }
  .top-left h1 {
    font-size: 12.8pt;
    font-weight: 800;
    letter-spacing: -0.01em;
    color: #ffffff;
    line-height: 1.15;
  }
  .top-left .sub {
    font-size: 6.95pt;
    color: #7dd3fc;
    margin-top: 0.4mm;
    font-weight: 600;
  }
  .top-left .sub span.em {
    color: #6ee7b7;
  }
  .top-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.95mm;
    flex-shrink: 0;
  }
  .pill-row {
    display: flex;
    gap: 1.4mm;
    align-items: center;
  }
  .hpill {
    font-size: 6.55pt;
    font-weight: 600;
    padding: 0.42mm 2.0mm;
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

  /* 2. UPPER 3-BOX ARCHITECTURE TIER */
  .upper-tier {
    display: grid;
    grid-template-columns: 127mm 12mm 135mm 12mm 124.4mm;
    align-items: stretch;
    flex-shrink: 0;
  }
  .u-card {
    border-radius: 2.2mm;
    padding: 1.65mm 2.65mm;
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
    font-size: 6.15pt;
    font-weight: 800;
    letter-spacing: 0.03em;
    margin-bottom: 0.3mm;
  }
  .u-card.amber .u-eyebrow { color: #b45309; }
  .u-card.blue .u-eyebrow { color: #0369a1; }
  .u-card.emerald .u-eyebrow { color: #047857; }
  .u-title {
    font-size: 8.0pt;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 0.5mm;
    line-height: 1.16;
  }
  .u-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.42mm;
  }
  .u-list li {
    font-size: 6.55pt;
    line-height: 1.22;
    color: #1e293b;
    padding-left: 1.9mm;
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
    gap: 0.35mm;
    padding: 0 0.4mm;
  }
  .u-conn .c-lbl { font-size: 6.05pt; font-weight: 800; color: #0369a1; line-height: 1.15; }
  .u-conn.em .c-lbl { color: #047857; }
  .u-conn .c-arr { font-size: 10.4pt; font-weight: 900; color: #0284c7; line-height: 1; }
  .u-conn.em .c-arr { color: #059669; }

  /* 3. MIDDLE 7-COLUMN × 4-CARD LAYER GRID */
  .cols-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1.85mm;
    flex: 1;
    min-height: 0;
  }
  .col {
    background: #ffffff;
    border: 0.32mm solid #cbd5e1;
    border-radius: 2.1mm;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }
  .col-head {
    padding: 1.35mm 1.95mm;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.9mm;
    flex-shrink: 0;
  }
  .col-head h3 { font-size: 7.05pt; font-weight: 800; line-height: 1.14; }
  .col-badge {
    font-size: 6.0pt;
    font-weight: 700;
    padding: 0.25mm 1.2mm;
    border-radius: 99mm;
    background: rgba(255, 255, 255, 0.22);
    white-space: nowrap;
    flex-shrink: 0;
  }
  .col-sub {
    padding: 0.72mm 1.75mm;
    font-size: 6.2pt;
    color: #334155;
    background: #f8fafc;
    border-bottom: 0.24mm solid #e2e8f0;
    line-height: 1.16;
    flex-shrink: 0;
  }
  .col-body {
    padding: 1.05mm 1.45mm;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 0.9mm;
    flex: 1;
    min-height: 0;
  }
  .mcard {
    border: 0.26mm solid #cbd5e1;
    border-radius: 1.5mm;
    padding: 1.0mm 1.45mm;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    gap: 0.3mm;
    flex: 1;
  }
  .mcard.custom { background: #f8fbff; border-color: #93c5fd; }
  .mcard-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6mm;
  }
  .mcard-title { font-size: 6.75pt; font-weight: 800; color: #0f172a; line-height: 1.13; }
  .mtag {
    font-size: 5.8pt;
    font-weight: 700;
    padding: 0.12mm 0.9mm;
    border-radius: 0.85mm;
    background: #eff6ff;
    color: #1d4ed8;
    border: 0.18mm solid #bfdbfe;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .mtag.odd17 { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
  .mtag.sec { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
  .mcard-role { font-size: 6.3pt; font-weight: 700; color: #1e293b; line-height: 1.14; }
  .mcard-desc { font-size: 6.15pt; color: #334155; line-height: 1.19; }
  .col-foot {
    padding: 0.8mm 1.65mm;
    background: #f8fafc;
    border-top: 0.24mm solid #e2e8f0;
    font-size: 6.05pt;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.15;
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
    gap: 2.1mm;
    flex-shrink: 0;
  }
  .b-flow {
    background: #0b1f33;
    color: #f8fafc;
    border-radius: 2.2mm;
    padding: 1.55mm 2.7mm;
    display: flex;
    flex-direction: column;
    gap: 0.45mm;
  }
  .b-flow h4 { font-size: 6.7pt; font-weight: 800; color: #7dd3fc; letter-spacing: 0.025em; }
  .b-flow p { font-size: 6.15pt; line-height: 1.2; color: #e2e8f0; }
  .b-flow code {
    background: rgba(255, 255, 255, 0.13);
    color: #ffffff;
    border-color: rgba(125, 211, 252, 0.35);
    font-size: 6.0pt;
  }
  .b-rules {
    background: #fffafa;
    border: 0.34mm solid #fecdd3;
    border-radius: 2.2mm;
    padding: 1.55mm 2.6mm;
    display: flex;
    flex-direction: column;
    gap: 0.44mm;
  }
  .b-rules h4 { font-size: 6.7pt; font-weight: 800; color: #be123c; letter-spacing: 0.025em; }
  .b-rules p { font-size: 6.1pt; line-height: 1.19; color: #1e293b; }
</style>
</head>
<body>
<div class="canvas">

  <!-- 1. TOP DARK HEADER -->
  <header class="topbar">
    <div class="top-left">
      <h1>POLARITA S.R.O. — SOFTWAROVÁ A SERVEROVÁ ARCHITEKTURA · VERZE 2.7 (2026)</h1>
      <div class="sub">
        <span class="em">0 Kč licencí · 100 % Open-Source + 10 modulů Odd. 17 · 6+9 DB PostgreSQL · 0× MySQL/MongoDB</span> · Asterisk + WhisperX + Silero VAD + librosa + Zulip + Stalwart + Chatwoot
      </div>
    </div>
    <div class="top-right">
      <div class="pill-row">
        <span class="hpill">IČO: 14180324 · DIČ: CZ14180324 · ISDS: w9bbdva · Pobočka 101</span>
        <span class="hpill accent">Kanály: latest LTS &amp; latest · Ověřená matice kompatibility</span>
      </div>
      <div class="pill-row">
        <span class="hpill">polarita-hq (Ubuntu Server LTS · OpenZFS · 0 Dockeru · 0 veř. SIP portů)</span>
        <span class="hpill">20 ai = 470 USD/m (85+15 %) · Stage 1/2 Eval 20/20</span>
      </div>
    </div>
  </header>

  <!-- 2. UPPER 3-BOX TIER -->
  <section class="upper-tier">
    <div class="u-card amber">
      <div class="u-eyebrow">MULTIPLATFORMNÍ KLIENTI, 360° KARTA, OSOBNÍ QES &amp; TERÉN (LIDÉ 1001+)</div>
      <div class="u-title">5 platforem · 360° Karta + WebRTC · Linphone &amp; Zulip · PWA QR · YubiKey</div>
      <ul class="u-list">
        <li>Stanice <code>Windows (latest Pro)</code>, <code>Linux (latest LTS)</code> a <code>Apple macOS (latest)</code> · Mobily <code>Android (latest)</code> a <code>Apple iOS / iPadOS (latest)</code></li>
        <li><strong>360° Karta + „Pracuj“ + WebRTC softphone</strong>, <code>Linphone</code>, <code>Zulip</code>, <code>Thunderbird</code> a PWA (QR, <code>VAN-*</code>, <code>SCRAP-CU</code>, <code>DTM ČR</code>, <code>WhisperX</code>)</li>
        <li><strong>YubiKey</strong> (USB/NFC pro WebAuthn SSO) · osobní <code>QES</code> v <code>JSignPdf</code> na čipu <code>QSCD</code> (eObčanka přes USB / Bluetooth čtečku!) vs. pečeť <code>pyHanko</code></li>
      </ul>
    </div>

    <div class="u-conn">
      <div class="c-lbl">Headscale<br>VPN + SSO</div>
      <div class="c-arr">⇄</div>
      <div class="c-lbl">Decisions<br>&amp; Zulip</div>
    </div>

    <div class="u-card blue">
      <div class="u-eyebrow">ŘÍDICÍ MOZEK 20 ai (BLOK 7), ZULIP, METADATA KERNEL &amp; WORKER / JUDGE</div>
      <div class="u-title">Paperclip + Zulip · metadata-schema-kernel · AigisCode · Stage 1/2 Eval</div>
      <ul class="u-list">
        <li><code>Paperclip</code> (1 zdroj promptů z <code>Gitea</code>) + <code>Zulip</code> v <code>Bloku 7</code> · <code>Decisions</code> diff <code>mutation_confirm</code> · tvrdý strop <code>470 USD/m</code> (<code>85 % + 15 % P1</code>)</li>
        <li>Worktrees <code>wt-worker / wt-judge</code> · <code>Draivix/aigiscode (MIT)</code> + <code>Gitea CI</code> · dvoustupňový <code>Promptfoo</code> (<code>Stage 1</code> mocky v Bloku 7, <code>Stage 2</code> v Bloku 12)</li>
        <li><code>metadata-schema-kernel</code> (výhradně vlastní schémata v <code>db_erp_lhutnik</code>, 0 zásahů do vendor DB!) · <code>polarita-ads-mcp (PAUSED)</code> · <code>Nod</code></li>
      </ul>
    </div>

    <div class="u-conn em">
      <div class="c-lbl">Izolace<br>Incus IaC</div>
      <div class="c-arr">→</div>
      <div class="c-lbl">4 zóny +<br>Clean Room</div>
    </div>

    <div class="u-card emerald">
      <div class="u-eyebrow">FYZICKÝ SERVER, CELÁ FIRMA V INCUS &amp; 4 ZÓNY (0 DOCKERU · 6+9 DB PG · 0× MYSQL/MONGODB)</div>
      <div class="u-title">Server polarita-hq · Ubuntu Server LTS · OpenZFS</div>
      <ul class="u-list">
        <li>Zrcadlený <code>OpenZFS</code> nad <code>/srv/polarita/</code> · <code>Incus (latest)</code> (<code>LXC</code> + <code>OCI</code> + <code>KVM</code>) deklarativně řízený přes <code>OpenTofu (latest)</code></li>
        <li><strong>4 zóny:</strong> <code>dmz_edge</code> (<code>Caddy</code> + MX <code>Stalwart</code>) · <code>app_internal</code> (<code>Asterisk</code>, <code>Zulip</code>, <code>Chatwoot</code> za <code>oauth2-proxy</code>) · <code>data_vault</code> (<code>6+9 PG DB</code> + <code>OpenBao</code>) · <code>sandbox_airgap</code></li>
        <li><code>Restic REST Server (--append-only)</code> (nedělní datový drill <code>03:00</code> + čtvrtletní <strong>Full Bare-Metal / VM DR Drill</strong>) · <code>Checkmk Raw</code> + <code>Telegram</code> pager</li>
      </ul>
    </div>
  </section>

  <!-- 3. MIDDLE 7-COLUMN × 4-CARD GRID COVERING ALL 11 SOFTWARE LAYERS -->
  <main class="cols-grid">

    <!-- COL 1: 01-03 -->
    <section class="col c-purple">
      <div class="col-head">
        <h3>01–03 · OS, Incus &amp; Síť</h3>
        <span class="col-badge">Vrstvy 01–03</span>
      </div>
      <div class="col-sub">Serverový základ, kontejnery bez Dockeru, VPN a 0 veř. SIP portů.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">01 · Ubuntu Server &amp; OpenZFS</span>
            <span class="mtag">OS + FS</span>
          </div>
          <div class="mcard-role">Zrcadlený základ /srv/polarita/ + 5 klientských OS</div>
          <div class="mcard-desc"><code>Ubuntu Server (latest LTS)</code> se samoopravnými součty <code>OpenZFS</code> (na hostiteli jen OS + <code>Incus</code>); podpora <code>Win / Linux / macOS / Android / iOS</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">02 · Incus &amp; OpenTofu (IaC)</span>
            <span class="mtag">0 Dockeru</span>
          </div>
          <div class="mcard-role">Systémové LXC, nativní OCI kontejnery a KVM VM</div>
          <div class="mcard-desc">Jediný démon <code>Incus (latest)</code> s limity CPU/RAM a předpisem <code>OpenTofu (latest)</code> pro <code>dmz_edge</code>, <code>app_internal</code>, <code>data_vault</code> a <code>sandbox_airgap</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">03 · Headscale, Caddy &amp; SIP</span>
            <span class="mtag">VPN &amp; TLS</span>
          </div>
          <div class="mcard-role">Mesh VPN, HTTPS/MX hrana a odchozí SIPS/SRTP</div>
          <div class="mcard-desc"><code>Cloudflare DNS</code>, <code>Caddy (latest)</code> + MX <code>25/tcp Stalwart</code>, <strong>0 veřejných SIP portů</strong> (odchozí <code>SIPS/SRTP</code> <code>Asterisk</code>) a vlastní <code>Headscale (latest)</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">nftables, CrowdSec &amp; OpenSSH</span>
            <span class="mtag sec">IPS &amp; SSH</span>
          </div>
          <div class="mcard-role">Jaderný firewall, komunitní IPS a správa uzlů</div>
          <div class="mcard-desc">Striktní pravidla mezi zónami v <code>nftables</code>, detekce útoků <code>CrowdSec</code> a správa přes <code>OpenSSH</code> klíče.</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 17003 &amp; 17004 · 0 veř. SIP portů</div>
    </section>

    <!-- COL 2: 04 -->
    <section class="col c-teal">
      <div class="col-head">
        <h3>04 · Trezor &amp; Podpisy</h3>
        <span class="col-badge">Vrstva 04</span>
      </div>
      <div class="col-sub">OpenBao, Clean Room, Kanál R, 3vrstvý CaMeL a QES vs. pečeť.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">OpenBao + TPM + YubiKey</span>
            <span class="mtag sec">Trezor</span>
          </div>
          <div class="mcard-role">API klíče, SIPS/SRTP, DKIM, ISDS a pečetní certifikát</div>
          <div class="mcard-desc">Tajemství pouze v RAM (0 hesel v <code>.env</code>), <code>Read-Only</code> certifikát ISDS <code>w9bbdva</code>, <code>SIPS/SRTP</code>, DKIM, <code>.p12 EET 2.0</code> a <code>Break-Glass SEAL</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">Keycloak, oauth2-proxy &amp; PII</span>
            <span class="mtag">SSO &amp; PII</span>
          </div>
          <div class="mcard-role">OIDC SSO + forward-auth Chatwoot CE + Clean Room</div>
          <div class="mcard-desc"><code>Keycloak SSO</code> (<code>YubiKey</code> + <code>oauth2-proxy</code> a <code>Platform API</code> pro <code>Chatwoot CE</code>), <code>Clean Room</code> (0 PII ve Vaultu) a <code>Kanál R FAIL_CLOSED</code> (pravidla sledování).</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">3vrstvá ochrana CaMeL + Judge</span>
            <span class="mtag sec">CaMeL</span>
          </div>
          <div class="mcard-role">Airgap extrakce + tag + deterministické ACL mimo LLM</div>
          <div class="mcard-desc">1) <code>ClamAV + Dangerzone + WhisperX</code> v <code>sandbox_airgap (nic=none)</code>, 2) <code>&lt;untrusted_inbound_comm&gt;</code>, 3) ACL a <code>mutation_confirm</code> mimo úsudek modelu.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">Osobní QES vs. Pečeť pyHanko</span>
            <span class="mtag">QES / pečeť</span>
          </div>
          <div class="mcard-role">Čip QSCD (JSignPdf) vs. serverová pečeť (pyHanko)</div>
          <div class="mcard-desc">Osobní <code>QES</code> (<code>1001</code> / <code>SUB-1007</code> v <code>JSignPdf</code> na čipu <code>QSCD</code> — soukromý klíč nikdy v OpenBao!) vs. serverová pečeť <code>pyHanko</code> pro Stavební deník.</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 17004, 15001 &amp; 1001 · Acyklický Blok 4</div>
    </section>

    <!-- COL 3: 05-06 -->
    <section class="col c-sky">
      <div class="col-head">
        <h3>05–06 · 6+9 DB &amp; DR</h3>
        <span class="col-badge">Vrstvy 05–06</span>
      </div>
      <div class="col-sub">6 doménových + 9 servisních PG DB, 90d/LEGAL_HOLD a DR.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">05 · 6+9 DB PostgreSQL</span>
            <span class="mtag">data_vault</span>
          </div>
          <div class="mcard-role">Vlastní schémata vs. vendor migrace (0× MySQL · 0× MongoDB)</div>
          <div class="mcard-desc">6 doménových (<code>db_eshop</code>, <code>db_akademie</code>, <code>db_erp_lhutnik</code>, <code>db_gdpr_zkousky</code>, <code>db_hr_lide</code>, <code>db_paperclip</code>) + 9 servisních DB s jasným vlastníkem migrací.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">Garage (90d) &amp; WORM LEGAL_HOLD</span>
            <span class="mtag">90d / 10 l</span>
          </div>
          <div class="mcard-role">Dvouvrstvá retence hovorů, fotky, Gitea a archiv</div>
          <div class="mcard-desc"><code>Valkey</code>, fotky a <strong><code>90denní</code> stereo hovory</strong> v <code>Garage</code>, <code>Gitea</code> a WORM <code>legal-archive</code> (<strong><code>LEGAL_HOLD 3–10 let</code> dle promlčecích lhůt</strong>, <code>.zfo</code>, pasy CE, deníky).</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">06 · Restic REST (--append-only)</span>
            <span class="mtag sec">2× DR Drill</span>
          </div>
          <div class="mcard-role">Týdenní datová obnova + čtvrtletní Full DR Drill</div>
          <div class="mcard-desc"><code>Sanoid</code>, <code>pgBackRest</code> a <code>Restic REST Server (--append-only)</code>: v neděli <code>03:00</code> obnova všech <code>6+9</code> DB v <code>Incus</code> + čtvrtletní <strong>Full DR Drill</strong> na čistý stroj.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">Checkmk Raw + Telegram Pager</span>
            <span class="mtag">Monitoring</span>
          </div>
          <div class="mcard-role">Acyklický dohled od Bloku 6 do Bloku 11</div>
          <div class="mcard-desc">V <code>Bloku 6</code> primární out-of-band <code>Telegram</code> pager + SMTP (host, ZFS, Incus, OpenBao, MX relay); v <code>Bloku 7</code> připojení <code>Zulip #17-it-secops</code> a v <code>Bloku 11</code> SIP/poštovní jádro.</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 17003 &amp; 17004 · 6+9 DB · Týdenní + Full DR</div>
    </section>

    <!-- COL 4: 07-08 -->
    <section class="col c-crimson">
      <div class="col-head">
        <h3>07–08 · ai, ISDS &amp; 360°</h3>
        <span class="col-badge">Vrstvy 07–08</span>
      </div>
      <div class="col-sub">Paperclip + Zulip, ISDS PAUSED, 360° Karta a 3úrovňové OCPP.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">07 · Paperclip + Zulip (Blok 7)</span>
            <span class="mtag">20 ai</span>
          </div>
          <div class="mcard-role">Strop 470 USD (85+15 %), 1 zdroj promptů a Zulip</div>
          <div class="mcard-desc"><code>Paperclip</code> + <code>Zulip + LiveKit</code> přímo v <code>Bloku 7</code>, <code>wt-worker/judge</code>, <code>claude-powerline-rust</code> a tvrdý stop všech API při <code>100 %</code> stropu <code>470 USD</code>.</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">metadata-schema-kernel &amp; Eval</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">Vlastní schémata + Ads MCP PAUSED + Stage 1/2</div>
          <div class="mcard-desc"><code>metadata-schema-kernel</code> (jen <code>db_erp_lhutnik</code>), <code>polarita-ads-mcp</code> (<code>PAUSED</code> + Spend Cap) a dvoustupňový <code>Promptfoo</code> (<code>Stage 1</code> &amp; <code>Stage 2</code> = <code>20/20</code>).</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">08 · Vault (0 PII) &amp; ISDS Bridge</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">SilverBullet + isds-podatelna-bridge (czebox.cz)</div>
          <div class="mcard-desc"><code>SilverBullet</code> (0 HR karet!); <code>libdatovka</code> čte <code>Po–Pá 06:50</code> jen při aktivní službě <code>1001 / Break-Glass</code> — při neobsazené nepřítomnosti <code>PAUSED</code> (doručení / fikce)!</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">360° Karta, Matice &amp; 3× OCPP</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">case_id · Mapy.cz · 48h šanony · 3úrovňové OCPP</div>
          <div class="mcard-desc"><strong>360° Karta + WebRTC + #t=MM:SS</strong>, matice zdrojů dle úkolu + <code>Mapy.cz</code>, <code>DTM ČR</code>, Stavební deník a <code>OCPP</code> (<code>Read-Only</code> / <code>Reset</code> / <code>UpdateFirmware</code> s <code>mutation_confirm</code>).</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 11001, 17001 &amp; 14005 · ISDS PAUSED · 3× OCPP</div>
    </section>

    <!-- COL 5: 09 -->
    <section class="col c-amber">
      <div class="col-head">
        <h3>09 · E-shop, WMS &amp; LMS</h3>
        <span class="col-badge">Vrstva 09</span>
      </div>
      <div class="col-sub">Web SVJ, polarita.eu, Elektro WMS, Moodle LTS a Umami.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">Astro + WebChat + Kalkulačka SVJ</span>
            <span class="mtag">polarita.cz</span>
          </div>
          <div class="mcard-role">Rychlý web, 48h šanony, Chatwoot a Umami nad PG</div>
          <div class="mcard-desc"><code>Astro + TS + Tailwind</code> (<code>llms.txt</code>), <strong>Kalkulačka SVJ</strong> (<code>/kalkulacka-svj</code>), <code>/prevzeti-sanonu</code>, <code>Chatwoot WebChat</code>, <code>Umami</code> nad PG a <code>Ecomail</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">MedusaJS + Balíkobot + RMA</span>
            <span class="mtag">polarita.eu</span>
          </div>
          <div class="mcard-role">B2C/B2B e-shop a oddělený complaint_asserted_at</div>
          <div class="mcard-desc">B2B ceníky (<code>Certified Partner SUB</code>), <code>Balíkobot</code>, Fio QR a v RMA oddělený <code>received_at</code> vs. neměnný <code>complaint_asserted_at</code> (lhůta vyřízení reklamace).</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">Vlastní modul elektro-wms</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">VAN-*, S/N, PHE, baterie &gt; 2 kWh a SCRAP-CU</div>
          <div class="mcard-desc">Rezervace staveb, <code>VAN-*</code> (svěřené hodnoty), bubny, <code>S/N</code> + B2B záruky, pas rozváděče, <code>PHE</code>, pasy baterií pro LMT, EV a průmyslové baterie &gt; 2 kWh od <code>18. 2. 2027</code> a <code>SCRAP-CU</code> (přenesená daň).</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">Moodle LTS (PHP matice) &amp; Bridge</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">Podporovaná větev PHP-FPM + poučení vs. 3čl. komise</div>
          <div class="mcard-desc"><code>Moodle (latest LTS)</code> nad ověřenou kompatibilní větví <code>PHP-FPM</code>; <code>compliance-bridge</code> rozlišuje osobu poučenou (bez komise) a zkoušky před 3čl. komisí s <code>QES</code> podpisem <code>1001</code>.</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 17002, 13001 &amp; 14004 · Matice Moodle/PHP</div>
    </section>

    <!-- COL 6: 10 -->
    <section class="col c-slate">
      <div class="col-head">
        <h3>10 · CAD, Rozváděče &amp; Revize</h3>
        <span class="col-badge">Vrstva 10</span>
      </div>
      <div class="col-sub">QElectroTech, LibreDWG, pasy rozváděčů NN a negativní revize.</div>
      <div class="col-body">
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">QElectroTech &amp; Průmyslový CAD</span>
            <span class="mtag">Produkce</span>
          </div>
          <div class="mcard-role">Schémata .qet + LibreDWG/ezdxf/IfcOpenShell</div>
          <div class="mcard-desc">Produkční elektro schémata v <code>QElectroTech</code> (značky dle platné normy), desktop <code>LibreCAD / FreeCAD / LibreOffice</code> a bez-síťové čtení výkresů v <code>sandbox_airgap</code>.</div>
        </div>
        <div class="mcard">
          <div class="mcard-top">
            <span class="mcard-title">Pilot CadCraft vs. ArtCraft</span>
            <span class="mtag">Apache</span>
          </div>
          <div class="mcard-role">getcadcraft.com (AEC) ≠ getartcraft.com (grafika)</div>
          <div class="mcard-desc">Volitelný pilot AEC sady <code>CadCraft / BimCraft / TakeoffCraft / MarkupCraft</code> (The Data Design Group, <code>Apache</code>) — striktně oddělený od kreativního <code>ArtCraft</code>!</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">cad-urs-engine · DTM &amp; pasy NN</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">Normová báze (Vault) + platná norma rozváděčů NN</div>
          <div class="mcard-desc">Zámek výkopů <code>DTM ČR</code> (uspořádání sítí), normové výpočty nad normovou bází <code>03-Normy-a-Metodiky/</code> (<code>15002</code>) a Výrobní pasy dle <strong>platné normy rozváděčů NN + výpočet oteplení</strong>.</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">cad-urs-engine · ÚRS &amp; Revize</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">Kladné i negativní revize (NESCHOPNO) + .xc4</div>
          <div class="mcard-desc">9 vrstev přípomocí <code>.xc4</code>, vícepráce <code>#t=MM:SS</code>; <code>FAIL_CLOSED</code> na neúplné vstupy, ale při překročení limitů norem generuje návrh <strong>negativní revize <code>NESCHOPNO</code></strong> pro RT!</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 14001–14003 &amp; 15002 · Pasy NN · Neg. revize</div>
    </section>

    <!-- COL 7: 11 -->
    <section class="col c-green">
      <div class="col-head">
        <h3>11 · Finance, HR &amp; PBX</h3>
        <span class="col-badge">Vrstva 11</span>
      </div>
      <div class="col-sub">ORG-UOL, přednástupní JMHZ, vozidla, Asterisk a librosa.</div>
      <div class="col-body">
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">cz-sk-registry &amp; finance-uol</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">ADIS · DB mutex · odpovědnost 1001 + ORG-UOL</div>
          <div class="mcard-desc"><code>ARES/VIES/ADIS/ISIR/CEE/SK RPO</code> (vč. ručení za DPH) + DB mutex řad, <code>ISDOC/Peppol</code>, <code>EET 2.0</code>, MRR ledger a mzdy 2. den → smluvní <code>ORG-UOL</code> 3. prac. den.</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">PWA portal-spolupracovniku</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">Přednástupní JMHZ · směny ≥ 14d/3d · pravidla sledování</div>
          <div class="mcard-desc">Registrace ČSSZ / <code>JMHZ</code> <strong>před zahájením práce</strong>, směny ≥ 14d EMP / ≥ 3d BRI, DPČ ≤ 1/2 doby, 5r Osvědčení vs. 10r Oprávnění TIČR, QR a <code>WhisperX</code>.</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">Traccar + fleet-gps + Mapy.cz</span>
            <span class="mtag odd17">Odd. 17</span>
          </div>
          <div class="mcard-role">Matice zdrojů dle úkolu &amp; vozidla v obecném režimu</div>
          <div class="mcard-desc">Rezervace zdrojů dle úkolu (sklad bez blokace auta!) + trasy <code>Mapy.cz</code>; odpovědnost za měřidla a <code>VAN-*</code>, <strong>služební vozidla v obecném režimu odpovědnosti</strong>.</div>
        </div>
        <div class="mcard custom">
          <div class="mcard-top">
            <span class="mcard-title">Asterisk, librosa &amp; comm-gateway</span>
            <span class="mtag odd17">K1–K5</span>
          </div>
          <div class="mcard-role">PBX + Silero VAD + librosa + Stalwart + Chatwoot</div>
          <div class="mcard-desc"><code>Asterisk</code> (IVR s poučením GDPR, stereo), <code>WhisperX</code>, <code>Silero VAD + librosa</code> (<code>MIT/ISC</code>, jen <code>Kanál L</code>!), <code>Stalwart</code> (<code>JMAP/ManageSieve</code>), <code>Chatwoot</code> (<code>oauth2-proxy</code>) a router.</div>
        </div>
      </div>
      <div class="col-foot">Garanti: 16001, 18001, 16002 &amp; 17001 · Silero + librosa</div>
    </section>

  </main>

  <!-- 4. BOTTOM 2-BOX STRIP -->
  <footer class="bottom-strip">
    <div class="b-flow">
      <h4>SÍŤOVÝ TOK PŘES 4 ZÓNY A ACYKLICKÝ POSTUP ZPROVOZNĚNÍ PO BLOCÍCH 0–12 (DEN 0 → DEN 30 · GO-LIVE GATE 12/12) + BLOKY 13–19 (S1–S7) · VERZE 2.7</h4>
      <p><strong>1. Izolovaný tok dat a hovorů:</strong> Internet (HTTPS + MX <code>25/tcp Stalwart</code>, <code>0</code> veř. SIP portů) → <code>dmz_edge</code> (<code>Caddy + CrowdSec</code>) → <code>app_internal</code> (<code>Asterisk</code>; přepis <code>WhisperX + Silero VAD + librosa Kanál L</code> v <code>sandbox_airgap</code>, <code>Zulip</code>, <code>Chatwoot</code> za <code>oauth2-proxy</code>, 3vrstvý CaMeL <code>comm-gateway</code>, <code>360° Karta + WebRTC</code>, <code>MedusaJS + elektro-wms</code>, <code>Moodle LTS</code>) → <code>data_vault</code> (<code>6+9 DB PostgreSQL</code> + <code>OpenBao</code> + <code>Garage 90d</code> + <code>legal-archive LEGAL_HOLD</code>).</p>
      <p><strong>2. Bloky 0–6 (Den 0–12 · Základ, Trezor &amp; Data):</strong> <code>S1-min</code> smlouvy → <code>Ubuntu LTS + OpenZFS</code> → <code>Incus + OpenTofu</code> → <code>Headscale VPN</code> → <code>OpenBao + Keycloak</code> (<code>QES</code> vs. <code>pyHanko</code>) → <code>6+9 PG DB</code> + <code>Gitea</code> → <code>Restic REST (--append-only)</code> + <code>Checkmk + Telegram</code>.</p>
      <p><strong>3. Bloky 7–12 (Den 13–30 · Mozek ai, Moduly &amp; Go-Live):</strong> <code>Paperclip + Zulip</code> + <code>metadata-schema-kernel</code> + <code>Stage 1 Eval</code> → <code>ISDS Bridge (czebox.cz) + 360° Karta</code> → <code>S3-min + WMS + Moodle</code> → <code>QElectroTech + cad-urs-engine</code> → <code>ORG-UOL + JMHZ + Asterisk</code> → <code>Stage 2 Eval + Full DR Drill</code>.</p>
    </div>
    <div class="b-rules">
      <h4>12 PRAVIDEL SOFTWARU + 4 POJISTKY NEPŘEBÍRÁNÍ Z DRAIVIXU (VERZE 2.7)</h4>
      <p><strong>1. 0 Kč vendor lock-in</strong> (100 % open-source bez komerčního omezení + 10 modulů Odd. 17) · <strong>2. Ověřená matice kompatibility</strong> (např. <code>Moodle LTS</code> + podporovaná větev <code>PHP-FPM</code>) · <strong>3. 0 Dockeru, 6+9 PG DB, 0× MySQL/Mongo</strong> · <strong>4. 5 klientských OS</strong> · <strong>5. Clean Room (0 PII ve Vaultu) &amp; Kanál R FAIL_CLOSED</strong> · <strong>6. <code>metadata-schema-kernel</code> jen pro vlastní schémata</strong> · <strong>7. OpenBao + 3vrstvý CaMeL + QES vs. pečeť</strong> · <strong>8. Python Decimal + Typst</strong> · <strong>9. ISDS 06:50 jen ve službě (jinak <code>PAUSED</code>) + <code>PAUSED</code> ads</strong> · <strong>10. Platná norma rozváděčů NN, negativní revize &amp; pasy baterií pro LMT, EV a průmyslové baterie &gt; 2 kWh od 18. 2. 2027</strong> · <strong>11. Přednástupní <code>JMHZ</code> &amp; vozidla v obecném režimu</strong> · <strong>12. Stage 1/2 Eval 20/20 &amp; čtvrtletní Full DR Drill</strong> · <strong>4 pojistky:</strong> (a) odpovědnost <code>1001</code> za účetnictví + smluvní <code>ORG-UOL</code>; (b) 0 nočních samo-přepisů norem/HR; (c) HW <code>OpenBao + TPM + YubiKey</code>; (d) <code>Zulip + Asterisk + WhisperX + Silero VAD + librosa</code>.</p>
    </div>
  </footer>

</div>
</body>
</html>
"""


CHAPTER_META = [
    ("01", "01-operacni-systemy.md", "Blok 1 · VRSTVA 01 · OPERAČNÍ SYSTÉMY", "Hostitelský základ Ubuntu Server (latest LTS) + OpenZFS (příp. LVM thin snapshoty) a multiplatformní stanice i mobily"),
    ("02", "02-virtualizace-a-kontejnery.md", "Blok 2 · VRSTVA 02 · VIRTUALIZACE A KONTEJNERY", "Incus (latest) a OpenTofu (latest) · 4 izolované síťové zóny bez Dockeru na hostiteli"),
    ("03", "03-sit-vpn-firewall-a-proxy.md", "Blok 3 · VRSTVA 03 · SÍŤ, PRIVÁTNÍ VPN, FIREWALL A POŠTOVNÍ / SIP HRANA", "Cloudflare DNS, Caddy, MX 25/tcp Stalwart Mail, 0 veřejných SIP portů (odchozí SIPS/SRTP Asterisk), Headscale VPN a CrowdSec"),
    ("04", "04-bezpecnost-trezor-identita-a-podpis.md", "Blok 4 · VRSTVA 04 · BEZPEČNOST, TREZOR, OAUTH2-PROXY, 3VRSTVÝ CAMEL A QES VS. PEČEŤ", "OpenBao + TPM + YubiKey, Keycloak + oauth2-proxy (Chatwoot CE), Clean Room, zákaz emocí Kanál R a osobní QES (QSCD) vs. pyHanko"),
    ("05", "05-databaze-a-uloziste.md", "Blok 5 · VRSTVA 05 · 6 DOMÉNOVÝCH + 9 SERVISNÍCH DB POSTGRESQL, 90D AUDIO A LEGAL_HOLD ARCHIV", "Jasné vlastnictví migrací (vlastní schémata vs. vendor DB), 0× MySQL/MongoDB, DB mutex, Garage (90d) a ZFS legal-archive"),
    ("06", "06-zalohovani-a-monitoring.md", "Blok 6 · VRSTVA 06 · ZÁLOHOVÁNÍ 3-2-1-1-0 (TÝDENNÍ + ČTVRTLETNÍ DR DRILL) A MONITORING", "Restic REST Server (--append-only), Sanoid, nedělní obnova 6+9 DB, čtvrtletní Full DR Drill a Checkmk Raw + Telegram pager"),
    ("07", "07-ai-orchestrace-decisions-a-eval.md", "Blok 7 · VRSTVA 07 · ORCHESTRACE 20 ai, ZULIP HUB, METADATA KERNEL A DVOUSTUPŇOVÁ EVAL SUITE", "Paperclip + Zulip v Bloku 7, tvrdý strop 470 USD (85+15 %), metadata-schema-kernel, wt-worker/judge, AigisCode a Stage 1/2 Eval"),
    ("08", "08-pamet-vault-podatelna-spisy-lhutnik-a-kniha-objektu.md", "Blok 8 · VRSTVA 08 · VAULT (0 PII), ISDS (PAUSED), 360° KARTA, MATICE ZDROJŮ A 3ÚROVŇOVÉ OCPP", "SilverBullet, isds-podatelna-bridge (06:50 / PAUSED, czebox.cz), 360° Karta + WebRTC, Mapy.cz, Stavební deník a 3× OCPP"),
    ("09", "09-weby-eshop-a-akademie.md", "Blok 9 · VRSTVA 09 · WEBY (SVJ & WEBCHAT), E-SHOP (RMA), ELEKTRO WMS, MOODLE LTS A UMAMI", "Astro + Kalkulačka SVJ, MedusaJS + elektro-wms (baterie > 2 kWh od 18. 2. 2027, complaint_asserted_at), Moodle LTS s kompatibilní větví PHP-FPM a Umami"),
    ("10", "10-elektro-projekce-rozvadece-rozpocty-a-revize.md", "Blok 10 · VRSTVA 10 · QELECTROTECH, PILOT CADCRAFT, PASY ROZVÁDĚČŮ A NEGATIVNÍ REVIZE", "QElectroTech + LibreDWG/ezdxf (+ volitelný pilot CadCraft oddělený od ArtCraft) a cad-urs-engine (DTM ČR, platná norma pro rozváděče nízkého napětí, kladné i negativní revize)"),
    ("11", "11-finance-uol-hr-bozp-portal-flotila-a-komunikace.md", "Blok 11 · VRSTVA 11 · REGISTRY ADIS, ORG-UOL, PŘEDNÁSTUPNÍ JMHZ, PWA A ÚSTŘEDNA ASTERISK", "cz-sk-registry-kernel, finance-uol-marze-engine (ORG-UOL), PWA (přednástupní JMHZ, obecná odpovědnost za vozidla), Traccar a Asterisk + WhisperX + Silero VAD + librosa + Stalwart + Chatwoot"),
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
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    return sanitize_html_links(raw_html, source_rel, included_rels)


PACKAGE_META = [
    ("balicky/README.md", "ETAPA II A III · ROZCESTNÍK BALÍČKŮ S1–S7", "Přehled Bloků 13–19, pravidla aktivace a stav ve Verzi 2.7"),
    ("balicky/S1-generator-cistopisu/README.md", "Blok 13 · BALÍČEK S1 · GENERÁTOR PDF ČISTOPISŮ", "15 šablon v 8 sestavách, vzorová data, generátor HTML → PDF a manifest pro mutation_confirm"),
    ("balicky/S2-eval-suite/README.md", "Blok 14 · BALÍČEK S2 · EVAL SUITE 100+", "157 scénářů (20 základních + 137 rozšířených), referenční politika, deterministický hodnotitel a trendový report"),
    ("balicky/S3-konfigurator-a-tarify/README.md", "Blok 15 · BALÍČEK S3 · KONFIGURÁTOR A TARIFY MRR", "Jediný zdroj cen cenik.json (výchozí ceny schválil 1001), cenové jádro, konfigurátor a provizní matice"),
    ("balicky/S4-dilensky-terminal-a-pujcovna/README.md", "Blok 16 · BALÍČEK S4 · DÍLENSKÝ TERMINÁL A PŮJČOVNA", "Kiosk kompletace rozváděčů s kusovým ověřením podle platné normy a B2B půjčovna měřidel"),
    ("balicky/S5-podpis-a-hlasova-recepcni/README.md", "Blok 17 · BALÍČEK S5 · DVOUSTRANNÝ PODPIS A HLASOVÁ ai RECEPČNÍ", "Konektor esign-bridge (elektronický podpis smluv [R-03]) a noční voice-agent nad Asterisk ARI (povinnost oznámit, že jde o ai)"),
    ("balicky/S6-ziva-prirucka-e2e/README.md", "Blok 18 · BALÍČEK S6 · ŽIVÁ PŘÍRUČKA Z E2E TESTŮ", "Samo-dokumentující testy Playwright a řízená 30minutová smyčka Worker / Judge pro ne-normové UI"),
    ("balicky/S7-polarita-elektro-cloud/README.md", "Blok 19 · BALÍČEK S7 · POLARITA ELEKTRO CLOUD", "Oborový multi-tenant SaaS: brána Go / No-Go, Row-Level Security a Liability Firewall"),
]


def build_book_html() -> str:
    included_rels = {"software/00-SEZNAM-SOFTWARU-README.md"}
    for _, fname, _, _ in CHAPTER_META:
        included_rels.add(f"software/{fname}")
    for rel, _, _ in PACKAGE_META:
        included_rels.add(rel)

    readme_md = (SW_DIR / "00-SEZNAM-SOFTWARU-README.md").read_text(encoding="utf-8")
    readme_html = md_to_html(readme_md, "software/00-SEZNAM-SOFTWARU-README.md", included_rels)

    chapters_html_parts = []
    for num, fname, eyebrow_exact, banner_title in CHAPTER_META:
        rel = f"software/{fname}"
        raw_md = (SW_DIR / fname).read_text(encoding="utf-8")
        rendered = md_to_html(raw_md, rel, included_rels)
        chapters_html_parts.append(f"""
        <section class="chapter-section" id="{doc_slug(rel)}">
          <div class="part-banner">
            <div class="pb-eyebrow">ČÁST II · {eyebrow_exact} · SOUBOR {rel}</div>
            <div class="pb-title">{banner_title}</div>
          </div>
          <div class="md-content">
            {rendered}
          </div>
        </section>
        """)

    all_chapters_html = "\n".join(chapters_html_parts)

    package_html_parts = []
    for rel, eyebrow_exact, banner_title in PACKAGE_META:
        rendered = md_to_html((ROOT_STRUCT / rel).read_text(encoding="utf-8"), rel, included_rels)
        package_html_parts.append(f"""
        <section class="chapter-section" id="{doc_slug(rel)}">
          <div class="part-banner">
            <div class="pb-eyebrow">ČÁST III · {eyebrow_exact} · SOUBOR {rel}</div>
            <div class="pb-title">{banner_title}</div>
          </div>
          <div class="md-content">
            {rendered}
          </div>
        </section>
        """)
    all_packages_html = "\n".join(package_html_parts)

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<title>Polarita s.r.o. — Kompletní softwarová architektura a katalog promptů (Verze 2.7)</title>
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

  /* COVER PAGE */
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
    font-size: 29.5pt;
    font-weight: 900;
    letter-spacing: -0.02em;
    margin: 0 0 2.2mm 0;
    line-height: 1.08;
    color: #ffffff;
  }}
  .cov-sub {{
    font-size: 12.2pt;
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

  /* OVERVIEW / ARCHITECTURE DIAGRAM PAGES */
  .overview-page {{
    page-break-after: always;
    break-after: page;
    max-width: 100%;
  }}
  .zone-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2.6mm;
    margin: 2.4mm 0 3.2mm 0;
  }}
  .zone-box {{
    border: 0.35mm solid #cbd5e1;
    border-left: 1.4mm solid #0284c7;
    border-radius: 2.2mm;
    padding: 2.2mm 3.0mm;
    background: #f8fafc;
  }}
  .zone-box.dmz {{ border-left-color: #4f46e5; }}
  .zone-box.app {{ border-left-color: #0284c7; }}
  .zone-box.vault {{ border-left-color: #0d9488; }}
  .zone-box.airgap {{ border-left-color: #be123c; background: #fffafa; }}
  .zone-box h4 {{
    margin: 0 0 0.7mm 0;
    font-size: 9.0pt;
    color: #0f172a;
  }}
  .zone-box p {{
    margin: 0;
    font-size: 8.3pt;
    color: #334155;
    line-height: 1.36;
  }}
  .guardrail-box {{
    border: 0.35mm solid #fecdd3;
    border-left: 1.5mm solid #be123c;
    border-radius: 2.2mm;
    padding: 2.2mm 3.0mm;
    background: #fffafa;
    margin-top: 2.2mm;
    font-size: 8.2pt;
    line-height: 1.36;
    color: #1e293b;
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .guardrail-box h4 {{
    margin: 0 0 0.8mm 0;
    font-size: 8.9pt;
    color: #be123c;
  }}

  /* SECTION BANNERS */
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
</style>
</head>
<body>

  <!-- PAGE 1: DARK NAVY COVER -->
  <div class="cover-page">
    <div>
      <div class="cov-pill">GREENFIELD OPEN-SOURCE &amp; ai-first SOFTWARE BLUEPRINT · VERZE 2.7 · JÁDRO + BALÍČKY S1–S7 · 2026</div>
      <h1 class="cov-h1">POLARITA S.R.O.</h1>
      <div class="cov-sub">Kompletní softwarová, serverová a komunikační architektura společnosti + katalog realizačních promptů (Vrstvy 01–11 · Verze 2.7)</div>
      <p class="cov-lead">
        Souborná architektonická kniha pro vybudování čisté společnosti od nuly na serveru <code>polarita-hq</code>
        (<code>Ubuntu Server latest LTS</code> + zrcadlený <code>OpenZFS</code> <code>/srv/polarita/</code>) ·
        Virtualizace <code>Incus (latest)</code> + <code>OpenTofu (latest)</code> ve 4 síťových zónách bez Dockeru na hostiteli ·
        Vlastní mesh VPN <code>Headscale</code> · Trezor <code>OpenBao + TPM + YubiKey</code>, oddělení osobního <code>QES</code> (čip <code>QSCD</code>) od serverové pečeti <code>pyHanko</code> a jednotné <code>Keycloak SSO</code> + <code>oauth2-proxy</code> ·
        <code>6 doménových + 9 servisních databází PostgreSQL</code> (<code>0× MySQL</code>, <code>0× MongoDB</code>) s režimem <code>Clean Room</code> nad PII + Git/CI server <code>Gitea</code> ·
        Softwarová ústředna <code>Asterisk</code> (<code>WebRTC + Linphone</code>, <code>0</code> veř. SIP portů, stereo <code>90d</code> vs. <code>LEGAL_HOLD 3–10 let</code>),
        lokální přepis <code>WhisperX</code> (<code>#t=MM:SS</code>), komerčně neomezená urgence <code>Silero VAD + librosa</code> (<code>MIT / ISC</code>) výhradně nad <code>Kanálem L</code> (<code>Kanál R = FAIL_CLOSED</code>),
        týmový hub <code>Zulip</code> + <code>LiveKit</code> (<code>Blok 7</code>), pošta <code>Stalwart Mail</code>, omnichannel <code>Chatwoot CE</code> (za <code>oauth2-proxy</code>) a 8cestný router <code>comm-gateway</code> ·
        <code>metadata-schema-kernel</code> (vlastní schémata), <code>Paperclip</code> (strop <code>470 USD</code> = 85 % + 15 % P1), <code>Stage 1 &amp; 2 Eval Suite</code>, <code>QElectroTech</code> (+ pilot <code>CadCraft</code>), <code>cad-urs-engine</code> (platná norma pro rozváděče nízkého napětí, negativní revize), <code>cz-sk-registry-kernel</code>, <code>ORG-UOL</code> a přednástupní <code>JMHZ</code>.
      </p>
    </div>

    <div class="cov-grid">
      <div class="cov-stat">
        <div class="num">11 vrstev · Acyklicky</div>
        <div class="txt">Realizovatelné pořadí Bloků 0–12 (Den 0–30) bez dopředných závislostí + Stage 1/2 Eval</div>
      </div>
      <div class="cov-stat">
        <div class="num">0 Kč licencí · MIT/BSD/GPL</div>
        <div class="txt">100 % open-source bez komerčního omezení (Silero VAD + librosa, oauth2-proxy, QElectroTech) + 10 modulů Odd. 17</div>
      </div>
      <div class="cov-stat">
        <div class="num">6+9 DB PG · 0× MySQL</div>
        <div class="txt">6 doménových + 9 servisních DB PostgreSQL · týdenní obnova + čtvrtletní Full DR Drill</div>
      </div>
      <div class="cov-stat">
        <div class="num">5 klientských OS</div>
        <div class="txt">Plná multiplatformní svoboda pro lidi (1001+): Windows, Linux, Apple macOS, Android a Apple iOS / iPadOS</div>
      </div>
    </div>

    <div class="cov-meta">
      <div><strong>Subjekt:</strong> Polarita s.r.o. · IČO: <code>14180324</code> · DIČ: <code>CZ14180324</code> · Sp. zn. C 361683 (MS v Praze) · ISDS: <code>w9bbdva</code> (Podatelna <code>16002</code>)</div>
      <div><strong>Sídlo a výchozí pobočka:</strong> Pobočka <code>101</code> (<code>CZ-101</code> Praha — Centrála), Na Folimance 2155/15, 120 00 Praha 2</div>
      <div><strong>Statutární a odborný garant:</strong> Václav Šercl (os. č. <code>1001</code> · <code>STAT-1001</code> · TIČR E2A) · <strong>Garanti platformy:</strong> Oddělení <code>17</code> (<code>17001</code>–<code>17005</code>)</div>
      <div><strong>Soulad se strukturou:</strong> Verze 2.7 · Návrhová kniha + realizační prompty pro Bloky 0–12 (<code>Go-Live Gate 12/12</code>) · Plakát: <code>05-SOFTWAROVA-MAPA-A3-2026.pdf</code></div>
    </div>
  </div>

  <!-- PAGE 2: EXECUTIVE STRUCTURE & 4 ZONES -->
  <div class="overview-page">
    <h1>Přehled struktury dokumentu (Softwarová architektura · Verze 2.7)</h1>
    <p>
      Tato souborná kniha sjednocuje kompletní návrh softwarového, databázového, komunikačního a bezpečnostního vybavení společnosti <strong>Polarita s.r.o.</strong>
      v plném souladu s <strong>Verzí 2.7</strong> organizační struktury. Všechny vybrané nástroje dodržují zásadu <strong>nulového vendor lock-inu</strong>,
      ověřují matici vzájemné kompatibility vydání (např. <code>Moodle LTS</code> s podporovanou větví <code>PHP-FPM</code>) a respektují jasné vlastnictví databázových migrací.
    </p>

    <table>
      <thead>
        <tr>
          <th style="width: 20%;">Část knihy</th>
          <th style="width: 28%;">Zdrojové soubory v <code>software/</code></th>
          <th style="width: 52%;">Obsah a klíčové výstupy (Verze 2.7)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>ČÁST I</strong><br>Přehled, 6+9 DB a pořadí stavby</td>
          <td><a href="#{doc_slug('software/00-SEZNAM-SOFTWARU-README.md')}">00-SEZNAM-SOFTWARU-README.md</a></td>
          <td>Architektonické principy + <strong>4 pojistky nepřebírání z Draivixu</strong>, rozcestník všech 11 vrstev, mapa <strong>6 doménových + 9 servisních databází <code>PostgreSQL</code></strong> s vlastníky migrací, acyklické pořadí výstavby v <strong>Blocích 0–12</strong> (<code>Den 0–30</code>) a návaznost na <code>S1–S7</code>.</td>
        </tr>
        <tr>
          <td><strong>ČÁST II · Infrastruktura &amp; Bezpečnost</strong><br>(Vrstvy 01–06)</td>
          <td><code>01-operacni-systemy.md</code> až <code>06-zalohovani-a-monitoring.md</code></td>
          <td>Hostitel <code>Ubuntu Server (latest LTS)</code> + <code>OpenZFS</code>, <code>Incus + OpenTofu</code>, VPN <code>Headscale</code>, <code>Caddy</code> + MX <code>Stalwart</code>, <strong>0 veř. SIP portů</strong>, <code>OpenBao + TPM + YubiKey</code>, <strong>osobní <code>QES</code> (čip <code>QSCD</code>) vs. pečeť <code>pyHanko</code></strong>, <code>Keycloak + oauth2-proxy</code>, 3vrstvý <code>CaMeL</code>, <code>Restic REST Server (--append-only)</code> (týdenní + čtvrtletní Full DR Drill) a <code>Checkmk + Telegram</code>.</td>
        </tr>
        <tr>
          <td><strong>ČÁST II · Mozek ai, 10 modulů &amp; Ústředna</strong><br>(Vrstvy 07–11)</td>
          <td><code>07-ai-orchestrace-decisions-a-eval.md</code> až <code>11-finance-uol-hr-bozp-portal-flotila-a-komunikace.md</code></td>
          <td><code>Paperclip + Zulip</code> v Bloku 7, strop <code>470 USD</code> (85+15 %), <code>metadata-schema-kernel</code> (vlastní schémata), <code>Stage 1 &amp; 2 Promptfoo</code>, ISDS Bridge (<code>06:50</code> ve službě / <code>PAUSED</code>, <code>czebox.cz</code>), <strong>360° Karta + WebRTC</strong>, matice zdrojů + <code>Mapy.cz</code>, 3× <code>OCPP</code>, <code>elektro-wms</code> (baterie &gt; 2 kWh od 18. 2. 2027, RMA <code>complaint_asserted_at</code>), <code>Moodle LTS</code>, <code>QElectroTech + cad-urs-engine</code> (platná norma rozváděčů NN, negativní revize), <code>ORG-UOL</code>, přednástupní <code>JMHZ</code>, obecná odpovědnost za vozidla a <code>Asterisk + WhisperX + Silero VAD + librosa</code>.</td>
        </tr>
        <tr>
          <td><strong>ČÁST III · Rozvojové balíčky S1–S7</strong><br>(Bloky 13–19)</td>
          <td><a href="#{doc_slug('balicky/README.md')}">balicky/README.md</a> a <code>README.md</code> balíčků <code>S1</code> až <code>S7</code></td>
          <td>Řídicí dokumenty Rozvojové Etapy II a Strategické Etapy III: <code>S1</code> generátor PDF čistopisů, <code>S2</code> <code>Eval Suite 100+</code> (157 scénářů), <code>S3</code> konfigurátor a tarify MRR (výchozí ceny schválil <code>1001</code>), <code>S4</code> dílenský terminál a půjčovna, <code>S5</code> dvoustranný podpis a hlasová recepční, <code>S6</code> živá příručka z E2E testů a <code>S7</code> Polarita Elektro Cloud (brána <code>Go / No-Go</code>).</td>
        </tr>
      </tbody>
    </table>

    <h2>Architektura 4 izolovaných síťových zón na serveru polarita-hq (Incus + OpenTofu)</h2>
    <div class="zone-grid">
      <div class="zone-box dmz">
        <h4>1. Zóna dmz_edge (Veřejná hrana · HTTPS &amp; MX · 0 veř. SIP portů)</h4>
        <p>Vstup z internetu přes reverzní proxy <code>Caddy (latest)</code> a příchozí MX relay <code>Stalwart Mail</code> s IPS ochranou <code>CrowdSec</code> + <code>nftables</code>. Ústředna <code>Asterisk</code> nevystavuje žádný veřejný příchozí SIP port (registruje se odchozím <code>SIPS / SRTP</code>).</p>
      </div>
      <div class="zone-box app">
        <h4>2. Zóna app_internal (Aplikační, komunikační, ai a vývojová vrstva)</h4>
        <p>Kontejnery <code>Asterisk</code>, <code>Stalwart Mail</code>, <code>Zulip + LiveKit</code>, <code>Chatwoot CE</code> (za <code>oauth2-proxy</code>), <code>Astro</code>, <code>Umami</code>, <code>MedusaJS + elektro-wms</code>, <code>Moodle LTS</code>, <code>Paperclip</code>, <code>SilverBullet</code>, <code>Gitea</code>, <code>Paperless-ngx</code>, <code>pyHanko</code>, <code>Vikunja</code>, <code>Traccar</code> a <strong>10 modulů oddělení <code>17</code></strong> za <code>Headscale VPN + Keycloak SSO</code>.</p>
      </div>
      <div class="zone-box vault">
        <h4>3. Zóna data_vault (6+9 DB PostgreSQL, Clean Room, 90d Audio a WORM)</h4>
        <p>Striktně bez internetu: <code>6 doménových + 9 servisních DB PostgreSQL</code> (<code>0× MySQL/MongoDB</code>, DB mutex <code>SELECT FOR UPDATE</code>, <code>Clean Room</code> maskované pohledy), trezor <code>OpenBao</code>, <code>Valkey</code>, <code>Garage</code> (<code>90d</code> audio) a WORM <code>OpenZFS legal-archive</code> (<code>LEGAL_HOLD 3–10 let</code>).</p>
      </div>
      <div class="zone-box airgap">
        <h4>4. Zóna sandbox_airgap (Jednorázová bez-síťová karanténa nic = none)</h4>
        <p>Kontejnery a KVM VM v <code>Incus</code> s <strong>úplně odebraným síťovým rozhraním (<code>nic = none</code>)</strong> pro 1. vrstvu <code>CaMeL</code> očisty příloh a hlasových zpráv (<code>ClamAV + Dangerzone + WhisperX + Silero VAD + librosa</code> → <code>&lt;untrusted_inbound_comm&gt;</code>), <code>48h šanony</code> a čtení výkresů (<code>LibreDWG + ezdxf + IfcOpenShell + PyMuPDF</code>).</p>
      </div>
    </div>
  </div>

  <!-- PAGE 3: 10 CUSTOM MODULES OF DEPARTMENT 17 + 4 GUARDRAILS -->
  <div class="overview-page">
    <h2 style="margin-top: 1.0mm;">Přehled 10 vlastních softwarových modulů vývojového oddělení 17 (17001 &amp; 17002 · wt-worker / wt-judge)</h2>
    <table style="font-size: 8.0pt; line-height: 1.28; margin-bottom: 2.0mm;">
      <thead>
        <tr>
          <th style="width: 24%;">Vlastní modul</th>
          <th style="width: 8%;">Vrstva</th>
          <th style="width: 22%;">Technologický stack</th>
          <th style="width: 46%;">Hlavní účel a napojená databáze (Verze 2.7)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><code>metadata-schema-kernel</code></td>
          <td>07</td>
          <td><code>Python / TS + JSON/YAML</code></td>
          <td>Deklarativní generátor entit (<code>N1</code>, <code>F22</code>): generuje migrace, REST API (<code>OpenAPI + ETag</code>), formuláře a typované <code>MCP</code> nástroje <strong>výhradně pro vlastní schémata v <code>db_erp_lhutnik</code></strong> (0 zásahů do vendor schémat cizích aplikací).</td>
        </tr>
        <tr>
          <td><code>polarita-ads-mcp</code></td>
          <td>07 / 09</td>
          <td><code>Python / TS MCP (MIT fork)</code></td>
          <td>Auditovaný fork <code>Draivix/aidvertaiser</code>: Google/Meta Ads, Search Console + <code>Sklik API</code>, <code>Zboží.cz / Heureka</code> a <code>Ecomail</code>, <code>Umami + POAS</code> a pevný zámek nových kampaní v <code>PAUSED</code> se <code>Spend Cap</code>.</td>
        </tr>
        <tr>
          <td><code>isds-podatelna-bridge</code></td>
          <td>08</td>
          <td><code>Python + libdatovka</code></td>
          <td><code>Read-Only</code> čtení ISDS <code>w9bbdva</code> v <code>Po–Pá 06:50</code> <strong>jen při aktivní službě <code>1001 / Break-Glass</code></strong> (při neobsazené nepřítomnosti <code>PAUSED</code> kvůli doručovacím účinkům, testy na <code>czebox.cz</code>, <code>F01</code>).</td>
        </tr>
        <tr>
          <td><code>centralni-lhutnik-a-objekty</code></td>
          <td>08</td>
          <td><code>Python / TS + ocpp + Astro</code></td>
          <td><strong>360° Karta spisu (<code>case_id</code>) + „Pracuj“ + WebRTC + #t=MM:SS</strong>, <code>48h šanony</code>, matice zdrojů dle úkolu + <code>Mapy.cz</code>, <code>DTM ČR</code>, <strong>Stavební deník</strong> (pečeť <code>pyHanko</code>) a <strong>3úrovňové <code>OCPP</code></strong> v <code>db_erp_lhutnik</code>.</td>
        </tr>
        <tr>
          <td><code>elektro-wms</code></td>
          <td>09</td>
          <td><code>TS (MedusaJS) + Balíkobot</code></td>
          <td>Rezervace staveb, <code>VAN-*</code> (svěřené hodnoty), bubny, <code>S/N</code> + B2B záruky, pas rozváděče dle platné normy, <code>PHE</code>, pasy baterií pro LMT, EV a průmyslové baterie &gt; 2 kWh od <code>18. 2. 2027</code>, <code>SCRAP-CU</code> (přenesená daň) a RMA <code>complaint_asserted_at</code> v <code>db_eshop</code>.</td>
        </tr>
        <tr>
          <td><code>compliance-bridge</code></td>
          <td>09</td>
          <td><code>Python + Typst + pyHanko</code></td>
          <td>Rozlišení poučení osoby poučené (bez komise, ≤ 3 r.) a zkoušek elektrotechniků před 3čl. komisí, osobní <code>QES</code> podpis <code>1001</code> a výběr <code>Certified Partner SUB</code> nad <code>db_gdpr_zkousky</code> (<code>Clean Room</code>).</td>
        </tr>
        <tr>
          <td><code>cad-urs-engine</code></td>
          <td>10</td>
          <td><code>Python Decimal + Typst</code></td>
          <td>Zámek <code>DTM ČR</code> (uspořádání sítí), normová báze ve Vaultu (<code>15002</code>), <strong>Výrobní pasy dle platné normy rozváděčů NN + výpočet oteplení</strong>, 9vrstvé rozpočty <code>.xc4</code> a <strong>kladné i negativní revize (<code>NESCHOPNO</code>)</strong>.</td>
        </tr>
        <tr>
          <td><code>cz-sk-registry-kernel</code></td>
          <td>08 / 11</td>
          <td><code>Python + PostgreSQL + Valkey</code></td>
          <td>Sdílený CZ/SK základ: <code>ARES</code>, <code>VIES</code>, <strong><code>ADIS</code> (ručení za DPH)</strong>, <code>ISIR / CEE</code>, <code>ČNB</code>, <code>ISDS</code>, <code>SK RPO / RegisterUZ / IČ DPH</code> a <strong>atomický DB mutex číselných řad (<code>SELECT ... FOR UPDATE</code>)</strong>.</td>
        </tr>
        <tr>
          <td><code>finance-uol-marze-engine</code></td>
          <td>11</td>
          <td><code>Python Decimal + Typst</code></td>
          <td><code>Read-Only</code> UOL/banky (odpovědnost účetní jednotky <code>1001</code> + smluvní <code>ORG-UOL</code>), DPH (přenesená daňová povinnost, PHE), <code>ISDOC/Peppol</code>, <code>EET 2.0</code>, mzdy 2.–3. den a <strong>Partnerský ledger 10–15 % MRR</strong>.</td>
        </tr>
        <tr>
          <td><code>portal-spolupracovniku</code>, <code>fleet-gps-bridge</code> &amp; <code>comm-gateway</code></td>
          <td>11</td>
          <td><code>Astro PWA + WhisperX + librosa</code></td>
          <td><code>db_hr_lide</code> (0 PII ve Vaultu, přednástupní <code>JMHZ</code>, směny ≥ 14d/3d, obecná odpovědnost za vozidla), <code>Traccar</code> a <strong>8cestný <code>comm-gateway</code></strong> (<code>Asterisk + WhisperX + Silero VAD + librosa Kanál L + Stalwart + Chatwoot</code>).</td>
        </tr>
      </tbody>
    </table>

    <div class="guardrail-box">
      <h4>Čtyři vědomé architektonické pojistky Verze 2.7 — Co z obecných systémů (Draivix) nepřebíráme</h4>
      <strong>(a) Nikdy „Bez účetní“:</strong> zákonnou odpovědnost za účetnictví nese <code>Polarita s.r.o. (1001)</code> a odborným smluvním zpracovatelem přiznání, závěrky a mezd je kancelář <code>UOL (ORG-UOL)</code>. ·
      <strong>(b) Žádné nehlídané noční přepisy normového jádra:</strong> normové výpočty (<code>cad-urs-engine</code>), pasy rozváděčů dle platné normy a brána <code>db_hr_lide</code> podléhají <code>Draivix/aigiscode</code>, <code>Stage 1/2 Eval</code> a <code>mutation_confirm</code>. ·
      <strong>(c) Žádný webový trezor v prohlížeči a žádný export osobního QES klíče:</strong> strojová tajemství žijí v <code>RAM</code> přes <code>OpenBao + TPM + YubiKey</code>; osobní <code>QES</code> klíč zůstává výhradně v čipu <code>QSCD</code>. ·
      <strong>(d) Žádné komerčně omezené či limitované nástroje:</strong> nasazujeme 100% open-source <code>Zulip + Asterisk + WhisperX + Silero VAD + librosa (MIT/ISC)</code> + <code>Chatwoot CE</code> za <code>oauth2-proxy</code> a zákaz emocí na <code>Kanálu R</code> (<code>FAIL_CLOSED</code>).
    </div>
  </div>

  <!-- ČÁST I: MASTER CATALOG README -->
  <section class="chapter-section" id="{doc_slug('software/00-SEZNAM-SOFTWARU-README.md')}">
    <div class="part-banner">
      <div class="pb-eyebrow">ČÁST I · SOUBOR software/00-SEZNAM-SOFTWARU-README.md</div>
      <div class="pb-title">Katalog vybraného softwaru, 6 doménových + 9 servisních databází PostgreSQL, acyklické pořadí zprovoznění (Bloky 0–12 · Den 0–30 · Go-Live Gate 12/12) a balíčky S1–S7</div>
    </div>
    <div class="md-content">
      {readme_html}
    </div>
  </section>

  <!-- ČÁST II: LAYERS 01 TO 11 -->
  {all_chapters_html}

  <!-- ČÁST III: DEVELOPMENT PACKAGES S1-S7 (BLOCKS 13-19) -->
  {all_packages_html}

</body>
</html>
"""


def render_pdf(browser: Path, html_path: Path, pdf_path: Path) -> None:
    file_url = html_path.resolve().as_uri()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        file_url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(f"Chyba při tisku {pdf_path.name}: {res.stderr}")


def main() -> None:
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    browser = find_browser()
    print(f"Použitý prohlížeč: {browser}")

    POSTER_HTML_PATH.write_text(build_poster_html(), encoding="utf-8")
    BOOK_HTML_PATH.write_text(build_book_html(), encoding="utf-8")
    print("HTML předlohy softwaru Verze 2.7 vygenerovány v dočasné složce.")

    render_pdf(browser, POSTER_HTML_PATH, OUT_POSTER_PDF)
    print(f"Vytvořeno A3 PDF: {OUT_POSTER_PDF} ({OUT_POSTER_PDF.stat().st_size:,} B)")

    render_pdf(browser, BOOK_HTML_PATH, OUT_BOOK_PDF)
    print(f"Vytvořeno A4 PDF: {OUT_BOOK_PDF} ({OUT_BOOK_PDF.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
