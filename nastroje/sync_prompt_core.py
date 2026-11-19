# -*- coding: utf-8 -*-
"""
Insert the shared core of rules into the system prompt of all 20 ai employee cards.
Vloží společné jádro pravidel do systémového promptu všech 20 karet ai zaměstnanců.

EN: The single source of the shared rules is agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md
    (between the JADRO-START / JADRO-END markers). This script writes them as the last numbered
    section of the ```text block in chapter 4 (system prompt) of every card, preceded by one
    generated line with the agent's id, system id and monthly allocation taken from kanon.json,
    and tailored so that escalation rules never create self-escalation loops.
    Running it twice changes nothing. With --check nothing is written and exit code 1 means drift.
CZ: Jediným zdrojem společných pravidel je agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md
    (mezi značkami JADRO-START / JADRO-END). Skript je zapíše jako poslední číslovaný oddíl
    bloku ```text v kap. 4 (systémový prompt) každé karty, předřadí jim jeden generovaný
    řádek s číslem, systémovým ID a měsíčním podílem agenta z kanon.json a upraví odkazy na
    eskalace tak, aby nevznikaly smyčky sebe-eskalace.
    Opakované spuštění nic nemění. S --check se nic nezapisuje a návratový kód 1 znamená rozdíl.

Usage / Použití:  python nastroje/sync_prompt_core.py [--check]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "agenti-a-prompty"
CORE_PATH = CARDS_DIR / "00-SPOLECNE-JADRO-PROMPTU.md"
CANON_PATH = Path(__file__).resolve().parent / "kanon.json"

SECTION_TITLE = "SPOLEČNÉ JÁDRO PRAVIDEL (shodné pro všech 20 ai; zdroj: agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md)"
SECTION_RE = re.compile(r"^\d+\. SPOLEČNÉ JÁDRO PRAVIDEL\b")
TOP_SECTION_RE = re.compile(r"^(\d+)\. \S")
CHAPTER4_RE = re.compile(r"^## 4\.\s")
# Earlier hand-written variants of the shared paragraph that the core replaces.
# Dřívější ručně psané varianty společného odstavce, které jádro nahrazuje.
LEGACY_RE = re.compile(r"^(- TÝMOVÁ KOMUNIKACE ZULIP A |\d+\. TÝMOVÁ KOMUNIKACE ZULIP A |- Veškerou interní týmovou komunikaci s lidmi i ostatními ai agenty veď v týmovém hubu Zulip)")


def load_canon() -> dict:
    return json.loads(CANON_PATH.read_text(encoding="utf-8"))


def load_core() -> list[str]:
    """Core rule lines between the markers. / Řádky pravidel mezi značkami."""
    text = CORE_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.search(r"<!-- JADRO-START -->[ \t]*\n(.*?)\n[ \t]*<!-- JADRO-END -->", text, flags=re.DOTALL)
    if not match:
        raise ValueError("core markers JADRO-START / JADRO-END not found")
    lines = [line for line in match.group(1).split("\n") if line.strip()]
    if not lines or any(not line.startswith("- ") for line in lines):
        raise ValueError("every core rule must be a single line starting with '- '")
    return lines


def identity_line(agent: dict, total: int) -> str:
    return (
        f"- Jsi ai zaměstnanec č. {agent['id']} ({agent['sysid']}) společnosti Polarita s.r.o.; "
        f"tvůj jmenovitý měsíční podíl v rozpočtu je {agent['budget_usd']} USD uvnitř celofiremního stropu {total} USD "
        f"(85 % je tvá provozní kvóta a 15 % z podílu každého agenta tvoří sdílenou rezervu P1 uvnitř téhož stropu {total} USD; "
        f"při 100 % se placená volání zastaví do schválení v Decisions)."
    )


def personalize_core(core: list[str], agent: dict) -> list[str]:
    """Prevent self-escalation loops for ceo, klicnik, pravni-specialista and normovac."""
    sysid = agent["sysid"]
    out: list[str] = []
    for line in core:
        if sysid == "ceo":
            line = line.replace("eskaluj agentovi ceo", "eskaluj přímo jednateli 1001 v Decisions")
        elif sysid == "klicnik":
            line = line.replace(
                "nahlas agentovi klicnik",
                "zaznamenej jako bezpečnostní incident a eskaluj agentovi ceo a jednateli 1001",
            )
        elif sysid in ("pravni-specialista", "normovac"):
            line = line.replace(
                "vyžádej jej u agentů pravni-specialista nebo normovac",
                "založ požadavek na doplnění báze z úředního/licencovaného zdroje ke schválení v Decisions; "
                "u cizí gesce vyžádej podklad u druhého z dvojice pravni-specialista / normovac",
            )
        out.append(line)
    return out


def render(card_text: str, agent: dict, core: list[str], total: int) -> str:
    """Return the card with the shared core as the last section of its system prompt (chapter 4). / Vrátí kartu se společným jádrem."""
    eol = "\r\n" if "\r\n" in card_text else "\n"
    lines = card_text.replace("\r\n", "\n").split("\n")
    try:
        ch4 = next(i for i, line in enumerate(lines) if CHAPTER4_RE.match(line))
        start = next(i for i in range(ch4 + 1, len(lines)) if lines[i].strip() == "```text")
        end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "```")
    except StopIteration as exc:
        raise ValueError(f"card {agent['id']}: system prompt block ```text under chapter 4 not found") from exc
    body = lines[start + 1:end]
    cut = next((i for i, line in enumerate(body) if SECTION_RE.match(line)), None)
    if cut is not None:
        body = body[:cut]
    body = [line for line in body if not LEGACY_RE.match(line)]
    while body and not body[-1].strip():
        body.pop()
    numbers = [int(m.group(1)) for m in (TOP_SECTION_RE.match(line) for line in body) if m]
    personalized = personalize_core(core, agent)
    section = [f"{max(numbers, default=0) + 1}. {SECTION_TITLE}", identity_line(agent, total), *personalized]
    new_lines = lines[:start + 1] + body + [""] + section + lines[end:]
    return eol.join(new_lines)


def card_path(agent: dict) -> Path:
    matches = sorted(CARDS_DIR.glob(f"{agent['id']}-*.md"))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one card for {agent['id']}, found {len(matches)}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if any(argument != "--check" for argument in arguments):
        # EN: Never write on an unknown argument (e.g. --help). / CZ: Při neznámém argumentu (např. --help) nikdy nezapisuj.
        print("usage: python nastroje/sync_prompt_core.py [--check]", file=sys.stderr)
        return 2
    check_only = "--check" in arguments
    try:
        canon = load_canon()
        core = load_core()
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1
    drift = []
    for agent in canon["agents"]:
        try:
            path = card_path(agent)
            current = path.read_bytes().decode("utf-8")  # keep original line endings / zachovat původní konce řádků
            expected = render(current, agent, core, canon["budget_total_usd"])
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 1
        if current != expected:
            drift.append(path.name)
            if not check_only:
                path.write_bytes(expected.encode("utf-8"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verb = "differs" if check_only else "updated"
    for name in drift:
        print(f"{verb}: {name}")
    print(f"{len(canon['agents'])} cards checked, {len(drift)} {verb}")
    return 1 if (check_only and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
