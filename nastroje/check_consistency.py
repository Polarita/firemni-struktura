# -*- coding: utf-8 -*-
"""
Consistency check of the Polarita blueprint against the canon (nastroje/kanon.json).
Kontrola konzistence návrhu Polarita proti kanonu (nastroje/kanon.json).

EN: The same facts repeat in dozens of documents. This script fails (exit code 1) when a document,
    a package or a PDF builder drifts from the canon: version, agent ids / names / budgets, database
    and Zulip channel names, document counts, the shared prompt core, forbidden (already corrected)
    terms, and Markdown structure (links, tables, code fences, line endings).
CZ: Stejné údaje se opakují v desítkách dokumentů. Skript selže (návratový kód 1), když se dokument,
    balíček nebo generátor PDF rozejde s kanonem: verze, čísla / jména / rozpočty agentů, názvy
    databází a kanálů Zulip, počty dokumentů, společné jádro promptů, zakázané (již opravené)
    výrazy a struktura Markdownu (odkazy, tabulky, bloky kódu, konce řádků).

Usage / Použití:  python nastroje/check_consistency.py [--warnings]
"""

from __future__ import annotations

import functools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sync_prompt_core

ROOT = Path(__file__).resolve().parents[1]
CANON_PATH = HERE / "kanon.json"
CORE_DIRS = ("", "oddeleni", "software", "agenti-a-prompty")
SKIP_PARTS = {".git", "__pycache__", "vystup", "output", "audio", ".venv", "venv", "node_modules", "scratch"}
VERSION_RE = re.compile(
    r"Verz(?:e|i|í) (\d+\.\d+(?:\.\d+)?)|VERZE (\d+\.\d+(?:\.\d+)?)|"
    r"Version (\d+\.\d+(?:\.\d+)?)|Polarita-(\d+\.\d+(?:\.\d+)?)"
)
VERSION_SUFFIXES = (".md", ".py", ".json", ".yaml", ".yml", ".html", ".sql", ".ts")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


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


def core_markdown() -> list[Path]:
    """Markdown files of the core (root + three core folders). / Markdown soubory jádra."""
    files: list[Path] = []
    for folder in CORE_DIRS:
        files += sorted((ROOT / folder).glob("*.md"))
    return files


def all_text_files() -> list[Path]:
    """Every checked text file: core, packages and tools. / Všechny kontrolované textové soubory."""
    files = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and not SKIP_PARTS.intersection(path.relative_to(ROOT).parts) \
                and (path.suffix in VERSION_SUFFIXES or path.name == "pre-commit"):
            files.append(path)
    return files


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def check_structure(path: Path, text: str, report: Report) -> None:
    """Line endings, code fences, table columns and relative links of one Markdown file."""
    where = rel(path)
    crlf = text.count("\r\n")
    lone_lf = len(re.findall(r"(?<!\r)\n", text))
    if crlf and lone_lf:
        report.error(where, f"mixed line endings ({crlf} CRLF, {lone_lf} LF)")
    lines = text.replace("\r\n", "\n").split("\n")
    if sum(1 for line in lines if line.lstrip().startswith("```")) % 2:
        report.error(where, "unclosed code fence")
    in_fence = False
    header_columns = None
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        is_row = not in_fence and line.strip().startswith("|")
        if is_row:
            columns = len(re.sub(r"\\\|", "", line.strip()).strip("|").split("|"))
            if header_columns is None:
                header_columns = columns
            elif columns != header_columns:
                report.error(f"{where}:{number}", f"table row has {columns} columns, header has {header_columns}")
        else:
            header_columns = None
        if in_fence:
            continue
        for match in LINK_RE.finditer(line):
            target = match.group(1)
            if re.match(r"^(https?:|mailto:|#|/)", target) or "{{" in target or "[XX]" in target:
                continue
            if target.split("#")[0].lower().endswith(".pdf"):
                continue  # build output, not stored in Git / výstup sestavení, není uložen v Gitu
            if not (path.parent / target.split("#")[0]).exists():
                report.error(f"{where}:{number}", f"broken relative link {target}")


def check_versions(path: Path, text: str, canon: dict, report: Report) -> None:
    where = rel(path)
    if where in canon["version_allowlist_files"] or path.name in ("kanon.json", "test_check_consistency.py", "bump_version.py"):
        return
    for number, line in enumerate(text.split("\n"), 1):
        for match in VERSION_RE.finditer(line):
            found = next(group for group in match.groups() if group)
            if found != canon["version"]:
                report.error(f"{where}:{number}", f"version {found} differs from canon {canon['version']}")


def check_forbidden(path: Path, text: str, canon: dict, is_core: bool, report: Report) -> None:
    where = rel(path)
    if where.startswith("nastroje/") and path.name in ("kanon.json", "check_consistency.py", "test_check_consistency.py"):
        return
    for rule in canon["forbidden"]:
        if rule.get("scope") == "core" and not is_core:
            continue
        pattern = _compiled(rule["pattern"])
        for number, line in enumerate(text.split("\n"), 1):
            if pattern.search(line):
                report.error(f"{where}:{number}", f"forbidden term /{rule['pattern']}/ — {rule['reason']}")


def check_agents(path: Path, text: str, canon: dict, report: Report) -> None:
    """Agent number must never be paired with a foreign system id or name."""
    where = rel(path)
    by_id = {agent["id"]: agent for agent in canon["agents"]}
    sysids = {agent["sysid"] for agent in canon["agents"]}
    names = {agent["name"]: agent["id"] for agent in canon["agents"]}
    ids_alt = "|".join(re.escape(agent["id"]) for agent in canon["agents"])
    id_sysid_re = re.compile(rf"`?\b({ids_alt})\b`?\s+`?([a-z]+(?:-[a-z]+)*)\b")
    for number, line in enumerate(text.split("\n"), 1):
        for match in id_sysid_re.finditer(line):
            agent_id, word = match.groups()
            if agent_id in by_id and word in sysids and by_id[agent_id]["sysid"] != word:
                report.error(f"{where}:{number}", f"agent {agent_id} paired with system id {word}")
        for name, owner in names.items():
            for match in re.finditer(rf"\b({ids_alt})\b[^|.;\n\d]{{0,25}}" + re.escape(name), line):
                if match.group(1) != owner:
                    report.error(f"{where}:{number}", f"name {name} paired with agent {match.group(1)}")


def check_names(path: Path, text: str, canon: dict, report: Report) -> None:
    """Database and Zulip channel names must come from the canon."""
    where = rel(path)
    databases = set(canon["domain_databases"])
    channels = set(canon["zulip_channels"])
    for number, line in enumerate(text.split("\n"), 1):
        for name in re.findall(r"\bdb_[a-z]+(?:_[a-z]+)*\b", line):
            if name not in databases:
                report.error(f"{where}:{number}", f"unknown database {name}")
        for name in re.findall(r"(?<![\w/&])#1[1-9]-[a-z]+(?:-[a-z]+)*", line):
            if name not in channels:
                report.error(f"{where}:{number}", f"unknown Zulip channel {name}")
        for name in re.findall(r"\b(?:dmz|app|data|sandbox)_[a-z]+(?:_[a-z]+)*\b", line):
            if name not in canon["network_zones"]:
                report.error(f"{where}:{number}", f"unknown network zone {name}")


def check_database_sets(path: Path, text: str, canon: dict, report: Report) -> None:
    """
    EN: A number stated before "servisních" / "doménových" must match the canon, and a line that
        lists most service databases must list all of them.
    CZ: Počet uvedený před slovem „servisních“ / „doménových“ musí odpovídat kanonu a řádek, který
        vyjmenovává většinu servisních databází, je musí vyjmenovat všechny.
    """
    where = rel(path)
    expected = {"servisních": len(canon["service_databases"]), "doménových": len(canon["domain_databases"])}
    for number, line in enumerate(text.split("\n"), 1):
        for count, kind in re.findall(r"(\d+)[`*]{0,3}\s+(?:[^\W\d]+\s+){0,2}(servisních|doménových)\b", line):
            if int(count) != expected[kind]:
                report.error(f"{where}:{number}", f"states {count} {kind} databases, canon says {expected[kind]}")
        if "servisních" in line:
            named = [name for name in canon["service_databases"] if re.search(r"\b" + re.escape(name) + r"\b", line)]
            if 5 <= len(named) < len(canon["service_databases"]):
                missing = sorted(set(canon["service_databases"]) - set(named))
                report.error(f"{where}:{number}", f"service database list is incomplete, missing {missing}")


def check_budgets(canon: dict, report: Report) -> None:
    total = sum(agent["budget_usd"] for agent in canon["agents"])
    if total != canon["budget_total_usd"]:
        report.error("nastroje/kanon.json", f"agent budgets sum to {total}, canon total is {canon['budget_total_usd']}")
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


def check_counts(canon: dict, report: Report) -> None:
    documents = canon["documents"]
    actual = {
        "core_markdown": len(core_markdown()),
        # EN: Print PDFs are build outputs kept out of Git - count the outputs declared by the builders.
        # CZ: Tisková PDF jsou výstupy sestavení mimo Git - počítají se výstupy deklarované generátory.
        "core_pdf": sum(len(re.findall(r"^OUT_\w+_PDF = ", read(ROOT / "nastroje" / name), flags=re.MULTILINE))
                        for name in ("build_org_pdfs.py", "build_software_pdfs.py")),
        "agent_cards": len(list((ROOT / "agenti-a-prompty").glob("1*.md"))),
        "department_charters": len(list((ROOT / "oddeleni").glob("*.md"))),
        "software_layers": len(list((ROOT / "software").glob("*.md"))),
        "packages": len([p for p in (ROOT / "balicky").iterdir() if p.is_dir() and p.name.startswith("S")]),
    }
    for key, value in actual.items():
        if value != documents[key]:
            report.error("nastroje/kanon.json", f"documents.{key} = {documents[key]}, but {value} found on disk")
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
    core = sync_prompt_core.load_core()
    for agent in canon["agents"]:
        try:
            path = sync_prompt_core.card_path(agent)
            current = read(path)
            if current != sync_prompt_core.render(current, agent, core, canon["budget_total_usd"]):
                report.error(rel(path), "shared prompt core differs from 00-SPOLECNE-JADRO-PROMPTU.md (run sync_prompt_core.py)")
        except ValueError as err:
            report.error("agenti-a-prompty", str(err))


def run() -> Report:
    canon = json.loads(CANON_PATH.read_text(encoding="utf-8"))
    report = Report()
    if canon.get("release_tag") != f"Polarita-{canon['version']}":
        report.error("nastroje/kanon.json", f"release_tag {canon.get('release_tag')} differs from Polarita-{canon['version']}")
    core_files = set(core_markdown())
    long_lines = 0
    for path in all_text_files():
        text = read(path)
        is_core = path in core_files
        if path.suffix == ".md":
            check_structure(path, text, report)
            check_agents(path, text, canon, report)
            check_names(path, text, canon, report)
        if path.suffix in VERSION_SUFFIXES:
            check_versions(path, text, canon, report)
        if path.suffix == ".md" or path.name in ("build_org_pdfs.py", "build_software_pdfs.py"):
            check_database_sets(path, text, canon, report)
        check_forbidden(path, text, canon, is_core, report)
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
