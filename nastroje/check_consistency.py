# -*- coding: utf-8 -*-
"""
Consistency check of the Polarita blueprint against the canon (nastroje/kanon.json).
Kontrola konzistence návrhu Polarita proti kanonu (nastroje/kanon.json).

EN: The same facts repeat in dozens of documents. This script fails (exit code 1) when a document,
    a package or a PDF builder drifts from the canon: version, agent ids / names / budgets, company
    identifiers, the company-wide budget cap, database, network zone and Zulip channel names, document
    counts, the shared prompt core, forbidden (already corrected) terms, and Markdown structure
    (links including anchors and PDF names, tables, code fences, line endings).
    Checked are all files tracked by Git plus new files that are not ignored; outside a Git checkout
    (unpacked archive) the script walks the file system instead.
CZ: Stejné údaje se opakují v desítkách dokumentů. Skript selže (návratový kód 1), když se dokument,
    balíček nebo generátor PDF rozejde s kanonem: verze, čísla / jména / rozpočty agentů, identifikace
    firmy, celofiremní strop, názvy databází, síťových zón a kanálů Zulip, počty dokumentů, společné
    jádro promptů, zakázané (již opravené) výrazy a struktura Markdownu (odkazy včetně kotev a názvů
    PDF, tabulky, bloky kódu, konce řádků).
    Kontrolují se všechny soubory sledované Gitem a nové neignorované soubory; mimo Git checkout
    (rozbalený archiv) skript prochází souborový systém.

Usage / Použití:  python nastroje/check_consistency.py [--warnings]
Exit codes / Návratové kódy: 0 = no error / bez chyby, 1 = at least one error / alespoň jedna chyba, 2 = usage / chybné použití.
"""

from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sync_prompt_core

ROOT = Path(__file__).resolve().parents[1]
CANON_PATH = HERE / "kanon.json"
CORE_DIRS = ("", "oddeleni", "software", "agenti-a-prompty")

# EN: Used only without Git (unpacked archive): directories that never hold blueprint sources.
# CZ: Použije se jen bez Gitu (rozbalený archiv): složky, které nikdy neobsahují zdroje návrhu.
FALLBACK_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache"}
FALLBACK_SKIP_PREFIXES = ("balicky/S2-eval-suite/output/behy/",)  # local run reports (ignored by Git) / místní reporty běhů
BINARY_SUFFIXES = {".pdf", ".wav", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".woff", ".woff2", ".ttf", ".pyc"}
NO_GIT_ENV = "POLARITA_CHECK_NO_GIT"  # set to 1 to force the file-system walk / hodnota 1 vynutí procházení souborového systému

# EN: The checker, its tests and the canon necessarily contain planted defects and forbidden patterns.
# CZ: Kontrola, její testy a kanon nutně obsahují podstrčené vady a zakázané vzory.
SELF_FILES = {"nastroje/check_consistency.py", "nastroje/test_check_consistency.py"}
CANON_FILE = "nastroje/kanon.json"
VERSION_EXEMPT_FILES = SELF_FILES | {CANON_FILE, "nastroje/bump_version.py"}
BUILDERS = ("nastroje/build_org_pdfs.py", "nastroje/build_software_pdfs.py")
# EN: Zone names look like code identifiers ("data_dir"), so outside Markdown they are checked only on
#     lines that speak about a zone or a network.
# CZ: Názvy zón vypadají jako identifikátory v kódu („data_dir“), proto se mimo Markdown kontrolují jen
#     na řádcích, které mluví o zóně nebo síti.
ZONE_CONTEXT_SUFFIXES = (".yaml", ".yml", ".sql", ".json", ".html", ".txt")
ZONE_CONTEXT_RE = re.compile(r"(?i)z[óo]n|\bzone|network|\bsíť|\bsit[ěe]")
# EN: Fictitious counterparties of the sample contracts live here. / CZ: Zde žijí fiktivní protistrany vzorových smluv.
SAMPLE_PARTY_PREFIXES = ("balicky/S1-generator-cistopisu/data/", "balicky/S1-generator-cistopisu/vystup/",
                         "balicky/S1-generator-cistopisu/sablony/")

_SEP = r"[\s`*:]{1,5}"
# EN: One pattern for the check and for bump_version.py: every way the blueprint version is written.
# CZ: Jeden vzor pro kontrolu i pro bump_version.py: všechny tvary, jimiž se zapisuje verze návrhu.
VERSION_RE = re.compile(
    r"(?P<prefix>(?i:\bverz(?:e|i|í)\b)" + _SEP + r"|\bVersion\b" + _SEP + r"|Polarita-|(?i:\b(?:blueprint|návrh\w*)\s+v))"
    r"(?P<number>\d+\.\d+(?:\.\d+)?)"
)
LINK_RE = re.compile(r"\]\(([^)\n]*)\)")
REF_LINK_RE = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(\S+)")
HTML_LINK_RE = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"'\n]+)["']""")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
NBSP_RE = re.compile("[\u00a0\u202f\u2007]|&nbsp;|&#160;|&#xa0;", flags=re.IGNORECASE)


@functools.lru_cache(maxsize=None)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


class Report:
    """Collected findings. / Sebrané nálezy."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize(text: str) -> str:
    """
    EN: Text as the rules see it: LF line ends and plain spaces instead of non-breaking ones, so that
        "§ 6" written with a non-breaking space cannot slip through.
    CZ: Text, jak jej vidí pravidla: konce řádků LF a obyčejné mezery místo nezlomitelných, aby
        „§ 6“ zapsané s nezlomitelnou mezerou neproklouzlo.
    """
    return NBSP_RE.sub(" ", text.replace("\r\n", "\n"))


def core_markdown() -> list[Path]:
    """Markdown files of the core (root + three core folders). / Markdown soubory jádra."""
    files: list[Path] = []
    for folder in CORE_DIRS:
        files += sorted((ROOT / folder).glob("*.md"))
    return files


def _git_files() -> list[Path] | None:
    """Tracked + new not-ignored files, or None when Git cannot answer. / Sledované + nové neignorované soubory, nebo None."""
    if os.environ.get(NO_GIT_ENV) == "1":
        return None
    try:
        done = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    names = [name for name in done.stdout.decode("utf-8", errors="surrogateescape").split("\0") if name]
    files = sorted({ROOT / name for name in names if (ROOT / name).is_file()})
    return files or None


def _walk_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or FALLBACK_SKIP_DIRS.intersection(relative.parts):
            continue
        if relative.as_posix().startswith(FALLBACK_SKIP_PREFIXES):
            continue
        files.append(path)
    return files


def all_files() -> list[Path]:
    """
    EN: Every checked file: what Git tracks (or would track), else the whole folder tree.
    CZ: Všechny kontrolované soubory: co Git sleduje (nebo by sledoval), jinak celý strom složky.
    """
    files = _git_files()
    if files is None:
        files = _walk_files()
    return [path for path in files if path.suffix.lower() not in BINARY_SUFFIXES]


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


# --- Markdown structure / Struktura Markdownu ---------------------------------------------------

def github_slug(heading: str) -> str:
    """GitHub-style anchor of a heading (same rule as the PDF builders). / Kotva nadpisu ve stylu GitHubu."""
    heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)   # [text](url) -> text
    heading = re.sub(r"<[^>]+>", "", heading)
    return re.sub(r"[^\w\s-]", "", heading.lower(), flags=re.UNICODE).strip().replace(" ", "-")


@functools.lru_cache(maxsize=None)
def anchors_of(path: Path) -> frozenset[str]:
    """All anchors a Markdown file offers: heading slugs and explicit id / name attributes."""
    try:
        text = normalize(read(path))
    except (OSError, UnicodeDecodeError):
        return frozenset()
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    fence = None
    for line in text.split("\n"):
        marker = FENCE_RE.match(line)
        if marker:
            fence = None if fence == marker.group(1) else (fence or marker.group(1))
            continue
        if fence:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            slug = github_slug(heading.group(2))
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            anchors.add(slug if count == 0 else f"{slug}-{count}")
        for explicit in re.findall(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""", line):
            anchors.add(explicit.lower())
    return frozenset(anchors)


@functools.lru_cache(maxsize=None)
def _listing(folder: Path) -> frozenset[str]:
    try:
        return frozenset(os.listdir(folder))
    except OSError:
        return frozenset()


def resolve_exact(base: Path, target: str) -> Path | None:
    """
    EN: Resolve a relative link and require the exact letter case of every component, so that a link
        which works on Windows / macOS does not break on Linux.
    CZ: Vyhodnotí relativní odkaz a vyžaduje přesnou velikost písmen každé části cesty, aby odkaz
        funkční na Windows / macOS neselhal na Linuxu.
    """
    current = base
    for part in target.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            continue
        if part not in _listing(current):
            return None
        current = current / part
    return current


@functools.lru_cache(maxsize=None)
def known_pdfs() -> frozenset[str]:
    """
    EN: PDF files are build outputs kept out of Git; a link may only point to an output that a
        builder really produces (book / poster PDFs, clean copies of package S1).
    CZ: PDF jsou výstupy sestavení mimo Git; odkaz smí mířit jen na výstup, který některý generátor
        skutečně vytváří (knihy / plakáty, čistopisy balíčku S1).
    """
    names: set[str] = set()
    for builder in BUILDERS:
        try:
            names.update(re.findall(r'^OUT_\w+_PDF = ROOT_STRUCT / "([^"]+\.pdf)"', read(ROOT / builder), flags=re.MULTILINE))
        except OSError:
            pass
    s1 = ROOT / "balicky" / "S1-generator-cistopisu"
    for template in (s1 / "sablony").glob("*.md"):
        names.add(f"balicky/S1-generator-cistopisu/vystup/{template.stem}.pdf")
    return frozenset(names)


def _link_targets(line: str) -> list[str]:
    targets = []
    for inner in LINK_RE.findall(line):
        inner = inner.strip()
        if inner.startswith("<") and ">" in inner:
            inner = inner[1:inner.index(">")]
        else:
            inner = re.sub(r"""\s+(?:"[^"]*"|'[^']*')$""", "", inner)   # optional link title / nepovinný titulek odkazu
        targets.append(inner)
    reference = REF_LINK_RE.match(line)
    if reference:
        targets.append(reference.group(1).strip("<>"))
    targets.extend(HTML_LINK_RE.findall(line))
    return targets


def check_link(path: Path, number: int, target: str, report: Report) -> None:
    where = f"{rel(path)}:{number}"
    if not target or SCHEME_RE.match(target) or target.startswith("/") or "{{" in target or "[XX]" in target:
        return
    file_part, _, fragment = unquote(target).partition("#")
    if file_part.lower().endswith(".pdf"):
        resolved = os.path.normpath(os.path.join(path.parent, file_part))
        try:
            relative = Path(resolved).relative_to(ROOT).as_posix()
        except ValueError:
            relative = ""
        if relative not in known_pdfs():
            report.error(where, f"link to a PDF that no builder produces: {target}")
        return
    destination = path if not file_part else resolve_exact(path.parent, file_part)
    if destination is None or not destination.exists():
        report.error(where, f"broken relative link {target}")
        return
    if fragment and destination.suffix.lower() == ".md" and destination.is_file():
        if fragment.lower() not in anchors_of(destination):
            report.error(where, f"broken anchor #{fragment} in link {target}")


def check_structure(path: Path, text: str, report: Report) -> None:
    """Line endings, code fences, table columns, relative links and anchors of one Markdown file."""
    where = rel(path)
    crlf = text.count("\r\n")
    lone_lf = len(re.findall(r"(?<!\r)\n", text))
    if crlf and lone_lf:
        report.error(where, f"mixed line endings ({crlf} CRLF, {lone_lf} LF)")
    lines = normalize(text).split("\n")
    fence = None
    header_columns = None
    for number, line in enumerate(lines, 1):
        marker = FENCE_RE.match(line)
        if marker:
            fence = None if fence == marker.group(1) else (fence or marker.group(1))
            header_columns = None
            continue
        if fence:
            continue
        stripped = line.strip()
        starts_table = (header_columns is None and "|" in stripped and number < len(lines)
                        and "|" in lines[number] and TABLE_SEPARATOR_RE.match(lines[number]))
        is_row = stripped.startswith("|") or bool(starts_table) or (header_columns is not None and "|" in stripped)
        if is_row:
            columns = len(re.sub(r"\\\|", "", stripped).strip("|").split("|"))
            if header_columns is None:
                header_columns = columns
            elif columns != header_columns:
                report.error(f"{where}:{number}", f"table row has {columns} columns, header has {header_columns}")
        else:
            header_columns = None
        for target in _link_targets(line):
            check_link(path, number, target, report)
    if fence:
        report.error(where, "unclosed code fence")


# --- Canon rules / Pravidla kanonu --------------------------------------------------------------

def version_mentions(line: str):
    """Yield every match of a blueprint version mention on a line. / Vrací všechny zmínky o verzi návrhu na řádku."""
    return VERSION_RE.finditer(line)


def check_versions(path: Path, text: str, canon: dict, report: Report) -> None:
    where = rel(path)
    if where in canon["version_allowlist_files"] or where in VERSION_EXEMPT_FILES:
        return
    for number, line in enumerate(normalize(text).split("\n"), 1):
        for match in version_mentions(line):
            found = match.group("number")
            if found != canon["version"]:
                report.error(f"{where}:{number}", f"version {found} differs from canon {canon['version']}")


def check_forbidden(path: Path, text: str, canon: dict, is_core: bool, report: Report) -> None:
    where = rel(path)
    if where in SELF_FILES or where == CANON_FILE:
        return
    lines = normalize(text).split("\n")
    for rule in canon["forbidden"]:
        if rule.get("scope") == "core" and not is_core:
            continue
        pattern = _compiled(rule["pattern"])
        for number, line in enumerate(lines, 1):
            if pattern.search(line):
                report.error(f"{where}:{number}", f"forbidden term /{rule['pattern']}/ — {rule['reason']}")


def check_agents(path: Path, text: str, canon: dict, report: Report) -> None:
    """Agent number must never be paired with a foreign system id or name."""
    where = rel(path)
    if where in SELF_FILES:
        return
    by_id = {agent["id"]: agent for agent in canon["agents"]}
    by_sysid = {agent["sysid"]: agent for agent in canon["agents"]}
    names = {agent["name"]: agent["id"] for agent in canon["agents"]}
    ids_alt = "|".join(re.escape(agent["id"]) for agent in canon["agents"])
    sys_alt = "|".join(sorted((re.escape(sysid) for sysid in by_sysid), key=len, reverse=True))
    # EN: "15001 normovac", "`15001` `normovac`", "`15001` (`normovac`)", "15001 – normovac", "15001 · normovac".
    #     A table separator "|" is deliberately not bridged: neighbouring cells often name two different agents.
    # CZ: Oddělovač tabulky "|" se záměrně nepřeklenuje: sousední buňky často jmenují dva různé agenty.
    forward = _compiled(rf"(?<![\w-])({ids_alt})(?![\w-])[\s`*(:·–—-]{{1,6}}([a-z]+(?:-[a-z]+)*)(?![\w-])")
    backward = _compiled(rf"(?<![\w-])({sys_alt})(?![\w-])[\s`*]{{0,3}}\([\s`*]{{0,3}}({ids_alt})(?![\w-])")
    # EN: The nearest name after a number (lazy), so "17004 Roman Hájek a Marek Kovář" pairs 17004 only with the first one.
    # CZ: Nejbližší jméno za číslem (líně), takže „17004 Roman Hájek a Marek Kovář“ páruje 17004 jen s prvním.
    names_alt = "|".join(re.escape(name) for name in names)
    named = _compiled(rf"\b({ids_alt})\b[^|.;\n\d]{{0,25}}?({names_alt})")
    for number, line in enumerate(normalize(text).split("\n"), 1):
        if not re.search(r"\d{5}", line):
            continue
        for match in forward.finditer(line):
            agent_id, word = match.groups()
            if word in by_sysid and by_id[agent_id]["sysid"] != word:
                report.error(f"{where}:{number}", f"agent {agent_id} paired with system id {word}")
        for match in backward.finditer(line):
            word, agent_id = match.groups()
            if by_id[agent_id]["sysid"] != word:
                report.error(f"{where}:{number}", f"agent {agent_id} paired with system id {word}")
        for match in named.finditer(line):
            if match.group(1) != names[match.group(2)]:
                report.error(f"{where}:{number}", f"name {match.group(2)} paired with agent {match.group(1)}")


def check_names(path: Path, text: str, canon: dict, report: Report) -> None:
    """Database, Zulip channel and network zone names must come from the canon."""
    where = rel(path)
    if where in SELF_FILES:
        return
    databases = set(canon["domain_databases"])
    channels = set(canon["zulip_channels"])
    zones = set(canon["network_zones"])
    suffix = path.suffix.lower()
    for number, line in enumerate(normalize(text).split("\n"), 1):
        for name in re.findall(r"(?<![A-Za-z0-9_])db_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*(?![A-Za-z0-9_])", line):
            if name not in databases:
                report.error(f"{where}:{number}", f"unknown database {name}")
        # EN: Link targets are anchors of headings ("#12-neco"), not channels. / CZ: Cíle odkazů jsou kotvy nadpisů, ne kanály.
        without_links = LINK_RE.sub("]()", line)
        for name in re.findall(r"(?<![\w/&])#\d{2}-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", without_links):
            if name not in channels:
                report.error(f"{where}:{number}", f"unknown Zulip channel {name}")
        if suffix == ".md" or (suffix in ZONE_CONTEXT_SUFFIXES and ZONE_CONTEXT_RE.search(line)):
            for name in re.findall(r"(?<![A-Za-z0-9_])(?:dmz|app|data|sandbox)_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*(?![A-Za-z0-9_])", line):
                if name not in zones:
                    report.error(f"{where}:{number}", f"unknown network zone {name}")


CAP_RE = re.compile(r"(?i)\bstrop\w*([^\n.;|]{0,45}?)(?<![\d,.])(?<!\d )((?:\d{1,3}(?: \d{3})+|\d+)(?:[,.]\d+)?) USD")


def check_company(path: Path, text: str, canon: dict, report: Report) -> None:
    """
    EN: Company identifiers (company id, VAT id, data box id) and the company-wide budget cap must match the canon.
    CZ: Identifikace firmy (IČO, DIČ, ID datové schránky) a celofiremní strop musí odpovídat kanonu.
    """
    where = rel(path)
    if where in SELF_FILES or where == CANON_FILE:
        return
    company = canon["company"]
    total = str(canon["budget_total_usd"])
    sample_party = where.startswith(SAMPLE_PARTY_PREFIXES)
    for number, line in enumerate(normalize(text).split("\n"), 1):
        if not sample_party:
            for found in re.findall(r"\bIČO?\b[^0-9\n]{0,25}(?<!\d)(\d{8})(?!\d)", line):
                if found != company["ico"] and set(found) != {"0"}:
                    report.error(f"{where}:{number}", f"company id {found} differs from canon {company['ico']}")
            for found in re.findall(r"\bDIČ\b[^\n]{0,25}?\b(CZ\d{8,10})\b", line):
                if found != company["dic"] and set(found[2:]) != {"0"}:
                    report.error(f"{where}:{number}", f"VAT id {found} differs from canon {company['dic']}")
        if re.search(r"(?i)schránk|\bISDS\b", line):
            for found in re.findall(r"`([a-z0-9]{7})`", line):
                if re.search(r"\d", found) and re.search(r"[a-z]", found) and found != company["isds"]:
                    report.error(f"{where}:{number}", f"data box id {found} differs from canon {company['isds']}")
        # EN: The WHOLE amount is read (70, 470, 1470, "1 470", 470,50) - a wrong cap with fewer or more
        #     digits is a wrong cap too. Skipped: the cap of a single agent and an amount that belongs to
        #     another cell or to a later amount of the line.
        # CZ: Čte se CELÁ částka (70, 470, 1470, „1 470“, 470,50) - chybný strop s méně nebo více číslicemi
        #     je také chybný strop. Přeskakuje se strop jednotlivého agenta a částka, která patří do jiné
        #     buňky nebo k pozdější částce na řádku.
        for between, found in CAP_RE.findall(line):
            if re.search(r"(?i)agent|USD|[<{]", between):
                continue
            if found.replace(" ", "") != total:
                report.error(f"{where}:{number}", f"budget cap {found} USD differs from canon {total} USD")


def check_database_sets(path: Path, text: str, canon: dict, report: Report) -> None:
    """
    EN: A number stated before "servisních" / "doménových" must match the canon, and a line that
        lists most service databases must list all of them.
    CZ: Počet uvedený před slovem „servisních“ / „doménových“ musí odpovídat kanonu a řádek, který
        vyjmenovává většinu servisních databází, je musí vyjmenovat všechny.
    """
    where = rel(path)
    expected = {"servisních": len(canon["service_databases"]), "doménových": len(canon["domain_databases"])}
    for number, line in enumerate(normalize(text).split("\n"), 1):
        for count, kind in re.findall(r"(\d+)[`*]{0,3}\s+(?:[^\W\d]+\s+){0,2}(servisních|doménových)\b", line):
            if int(count) != expected[kind]:
                report.error(f"{where}:{number}", f"states {count} {kind} databases, canon says {expected[kind]}")
        if "servisních" in line:
            named = [name for name in canon["service_databases"] if re.search(r"\b" + re.escape(name) + r"\b", line)]
            if 5 <= len(named) < len(canon["service_databases"]):
                missing = sorted(set(canon["service_databases"]) - set(named))
                report.error(f"{where}:{number}", f"service database list is incomplete, missing {missing}")


def check_builder_agents(name: str, text: str, canon: dict, report: Report) -> None:
    """
    EN: Hand-written agent headings of the PDF builders ("11001 · NAME (ai · sysid · NN USD)") must match the canon.
    CZ: Ručně psané nadpisy agentů v generátorech PDF („11001 · JMÉNO (ai · sysid · NN USD)“) musí odpovídat kanonu.
    """
    by_id = {agent["id"]: agent for agent in canon["agents"]}
    for number, line in enumerate(text.split("\n"), 1):
        for agent_id, shown_name, sysid, budget in re.findall(r"\b(\d{5}) · ([^\"(]+?) \(ai · ([a-z-]+) · (\d+) USD\)", line):
            agent = by_id.get(agent_id)
            if agent is None:
                report.error(f"{name}:{number}", f"heading names unknown agent {agent_id}")
            elif (shown_name.strip().upper(), sysid, int(budget)) != (agent["name"].upper(), agent["sysid"], agent["budget_usd"]):
                report.error(f"{name}:{number}", f"heading of agent {agent_id} does not match the canon (name, system id, budget)")


def check_budgets(canon: dict, report: Report) -> None:
    total = sum(agent["budget_usd"] for agent in canon["agents"])
    if total != canon["budget_total_usd"]:
        report.error(CANON_FILE, f"agent budgets sum to {total}, canon total is {canon['budget_total_usd']}")
    readme = read(ROOT / "README.md")
    main_book = read(ROOT / "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md")
    for agent in canon["agents"]:
        row = re.search(r"^\| \*\*`" + agent["id"] + r"`\*\* \|.*$", readme, flags=re.MULTILINE)
        if not row or f"`{agent['budget_usd']} USD`" not in row.group(0) or agent["name"] not in row.group(0) \
                or f"`{agent['sysid']}`" not in row.group(0):
            report.error("README.md", f"catalogue row of agent {agent['id']} does not match the canon")
        row = re.search(r"^\|.*\[Karta " + agent["id"] + r"\].*$", main_book, flags=re.MULTILINE)
        if not row or f"| {agent['budget_usd']} USD |" not in row.group(0):
            report.error("00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md", f"personnel table row of agent {agent['id']} does not match the canon")
        cards = sorted((ROOT / "agenti-a-prompty").glob(f"{agent['id']}-*.md"))
        if len(cards) != 1 or not cards[0].name.startswith(f"{agent['id']}-{agent['sysid']}-"):
            report.error("agenti-a-prompty", f"card file of agent {agent['id']} is missing or misnamed")
            continue
        heading = read(cards[0]).split("\n", 1)[0]
        if agent["id"] not in heading or agent["name"] not in heading or f"`{agent['sysid']}`" not in heading:
            report.error(rel(cards[0]), "card heading does not match the canon (id, name, system id)")
    for builder in BUILDERS:
        check_builder_agents(builder, read(ROOT / builder), canon, report)


def check_counts(canon: dict, report: Report) -> None:
    documents = canon["documents"]
    actual = {
        "core_markdown": len(core_markdown()),
        # EN: Print PDFs are build outputs kept out of Git - count the outputs declared by the builders.
        # CZ: Tisková PDF jsou výstupy sestavení mimo Git - počítají se výstupy deklarované generátory.
        "core_pdf": sum(len(re.findall(r"^OUT_\w+_PDF = ", read(ROOT / name), flags=re.MULTILINE)) for name in BUILDERS),
        "agent_cards": len(list((ROOT / "agenti-a-prompty").glob("1*.md"))),
        "department_charters": len(list((ROOT / "oddeleni").glob("*.md"))),
        "software_layers": len(list((ROOT / "software").glob("*.md"))),
        "packages": len([p for p in (ROOT / "balicky").iterdir() if p.is_dir() and p.name.startswith("S")]),
    }
    for key, value in actual.items():
        if value != documents[key]:
            report.error(CANON_FILE, f"documents.{key} = {documents[key]}, but {value} found on disk")
    if len(canon["agents"]) != documents["agent_cards"]:
        report.error(CANON_FILE, f"documents.agent_cards = {documents['agent_cards']}, but the canon lists {len(canon['agents'])} agents")
    readme = read(ROOT / "README.md")
    stated_total = documents["core_markdown"] + documents["core_pdf"]
    for name in ("README.md", "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md", "nastroje/build_org_pdfs.py"):
        for found in re.findall(r"\*\*(\d+) dokumentů\*\*|všech \*{0,2}(\d+) (?:dokumentů|souborů)", read(ROOT / name)):
            number = int(next(group for group in found if group))
            if number != stated_total:
                report.error(name, f"states {number} documents, canon says {stated_total}")
    for found in re.findall(r"`(\d+) × \.md`", readme):
        if int(found) != documents["core_markdown"]:
            report.error("README.md", f"states {found} × .md, canon says {documents['core_markdown']}")


def check_prompt_core(canon: dict, report: Report) -> None:
    try:
        core = sync_prompt_core.load_core(ROOT)
    except (ValueError, OSError) as err:
        report.error("agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md", str(err))
        return
    for agent in canon["agents"]:
        try:
            path = sync_prompt_core.card_path(agent, ROOT)
            current = read(path)
            if current != sync_prompt_core.render(current, agent, core, canon["budget_total_usd"]):
                report.error(rel(path), "shared prompt core differs from 00-SPOLECNE-JADRO-PROMPTU.md (run sync_prompt_core.py)")
        except ValueError as err:
            report.error("agenti-a-prompty", str(err))


def check_file(path: Path, text: str, canon: dict, is_core: bool, report: Report) -> None:
    """All per-file rules. / Všechna pravidla nad jedním souborem."""
    where = rel(path)
    if path.suffix.lower() == ".md":
        check_structure(path, text, report)
    check_versions(path, text, canon, report)
    check_forbidden(path, text, canon, is_core, report)
    check_agents(path, text, canon, report)
    check_names(path, text, canon, report)
    check_company(path, text, canon, report)
    if path.suffix.lower() == ".md" or where in BUILDERS:
        check_database_sets(path, text, canon, report)


def run() -> Report:
    canon = json.loads(CANON_PATH.read_text(encoding="utf-8"))
    report = Report()
    if canon.get("release_tag") != f"Polarita-{canon['version']}":
        report.error(CANON_FILE, f"release_tag {canon.get('release_tag')} differs from Polarita-{canon['version']}")
    core_files = set(core_markdown())
    long_lines = 0
    for path in all_files():
        try:
            text = read(path)
        except UnicodeDecodeError:
            report.error(rel(path), "file is not valid UTF-8 (add a binary suffix to BINARY_SUFFIXES if it is not text)")
            continue
        is_core = path in core_files
        check_file(path, text, canon, is_core, report)
        if is_core:
            too_long = sum(1 for line in text.replace("\r\n", "\n").split("\n") if len(line) > canon["long_line_warning_chars"])
            long_lines += too_long
            if too_long:
                report.warn(rel(path), f"{too_long} lines longer than {canon['long_line_warning_chars']} characters")
    check_budgets(canon, report)
    check_counts(canon, report)
    check_prompt_core(canon, report)
    report.warn("core", f"{long_lines} lines longer than {canon['long_line_warning_chars']} characters in total")
    return report


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if any(argument != "--warnings" for argument in arguments):
        print("usage: python nastroje/check_consistency.py [--warnings]", file=sys.stderr)
        return 2
    report = run()
    for line in report.errors:
        print("ERROR  ", line)
    if "--warnings" in arguments:
        for line in report.warnings:
            print("WARNING", line)
    print(f"consistency check: {len(report.errors)} errors, {len(report.warnings)} warnings")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
