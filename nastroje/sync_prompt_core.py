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
    The tailoring replaces exact phrases of the core (table PERSONALIZATION); when a phrase is not
    found exactly once the script stops with an error instead of silently skipping the tailoring.
CZ: Jediným zdrojem společných pravidel je agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md
    (mezi značkami JADRO-START / JADRO-END). Skript je zapíše jako poslední číslovaný oddíl
    bloku ```text v kap. 4 (systémový prompt) každé karty, předřadí jim jeden generovaný
    řádek s číslem, systémovým ID a měsíčním podílem agenta z kanon.json a upraví odkazy na
    eskalace tak, aby nevznikaly smyčky sebe-eskalace.
    Opakované spuštění nic nemění. S --check se nic nezapisuje a návratový kód 1 znamená rozdíl.
    Personalizace nahrazuje přesné fráze jádra (tabulka PERSONALIZATION); když se fráze nenajde
    právě jednou, skript skončí chybou, místo aby personalizaci tiše vynechal.

Usage / Použití:  python nastroje/sync_prompt_core.py [--check]
"""

from __future__ import annotations

import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
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


# EN: Tailoring of the shared core per agent: system id -> list of (exact phrase of the core, replacement).
#     Every phrase must occur EXACTLY ONCE in the core, otherwise load_core() fails. When the wording of
#     the core changes, change the phrase here in the same commit.
# CZ: Personalizace společného jádra podle agenta: systémové ID -> seznam (přesná fráze jádra, náhrada).
#     Každá fráze se musí v jádru vyskytovat PRÁVĚ JEDNOU, jinak load_core() selže. Když se změní
#     znění jádra, uprav frázi zde v témže commitu.
_BASE_REQUEST_PHRASE = "vyžádej jej u příslušného garanta báze (pravni-specialista / normovac; případně vzájemným posudkem přes ceo)"
PERSONALIZATION: dict[str, list[tuple[str, str]]] = {
    # EN: 11001 is the top of the ai line - it escalates to the owner and the Decisions queue runs through it.
    # CZ: 11001 je vrchol linie ai - eskaluje jednateli a fronta Decisions vede přes něj.
    "ceo": [
        ("eskaluj agentovi ceo", "eskaluj přímo jednateli 1001 v Decisions"),
        ("Do fronty Decisions jde vše přes agenta ceo", "Do fronty Decisions jde vše přes tebe"),
        ("na návrh agenta ceo", "na tvůj návrh"),
    ],
    # EN: 14005 keeps the case file and the customer communication itself.
    # CZ: 14005 vede spis a komunikaci se zákazníkem sám.
    "zakazky": [
        ("vyžádej přes agenta zakazky, který vede spis a komunikaci se zákazníkem",
         "vyžádej sám konceptem zprávy zákazníkovi ke schválení v Decisions, protože spis a komunikaci se zákazníkem vedeš ty"),
    ],
    # EN: 17005 only releases the P1 reserve technically. / CZ: 17005 rezervu P1 jen technicky uvolňuje.
    "ai-provoz": [
        ("agent ai-provoz ji pouze technicky uvolňuje a nikdy ne sám sobě", "ty ji pouze technicky uvolňuješ a nikdy ne sám sobě"),
    ],
    # EN: 17004 cannot report to itself; its own outputs are reviewed by 17003 and the owner.
    # CZ: 17004 nemůže hlásit sám sobě; jeho vlastní výstupy posuzuje 17003 a jednatel.
    "klicnik": [
        ("agenta klicnik probudí", "tebe probudí"),
        ("přímo nahlas agentovi klicnik",
         "ty sám veď jako bezpečnostní incident s nezávislým posouzením agentem spravce-site a jednatelem 1001"),
    ],
    # EN: A guarantor of the base never refers to itself: 15001 -> normovac or the attorney, 15002 -> pravni-specialista.
    # CZ: Garant báze nikdy neodkazuje sám na sebe: 15001 -> normovac nebo advokát, 15002 -> pravni-specialista.
    "pravni-specialista": [
        (_BASE_REQUEST_PHRASE,
         "záznam ve své gesci doplň z úředního nebo licencovaného zdroje a předlož jej přes Decisions k nezávislému posouzení "
         "agentu normovac nebo advokátovi; záznam v gesci agenta normovac vyžádej u něj"),
    ],
    "normovac": [
        (_BASE_REQUEST_PHRASE,
         "záznam ve své gesci doplň z úředního nebo licencovaného zdroje a předlož jej přes Decisions k nezávislému posouzení "
         "agentu pravni-specialista; záznam v gesci agenta pravni-specialista vyžádej u něj"),
    ],
}

# EN: Split of the nominal monthly share of an agent: operating quota (hard limit of the agent) and the
#     shared P1 reserve. / CZ: Dělení jmenovitého měsíčního podílu agenta: provozní kvóta (tvrdý limit
#     agenta) a sdílená rezerva P1.
OPERATING_QUOTA_PCT = 85
RESERVE_PCT = 100 - OPERATING_QUOTA_PCT


def usd(amount: Decimal) -> str:
    """Two decimal places with the Czech decimal comma. / Dvě desetinná místa s českou desetinnou čárkou."""
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)).replace(".", ",")


def load_canon() -> dict:
    return json.loads(CANON_PATH.read_text(encoding="utf-8"))


def validate_personalization(core: list[str]) -> None:
    """
    EN: Every tailoring phrase must be present exactly once in the core; otherwise the tailoring
        would be silently lost (and an agent would be told to escalate to itself).
    CZ: Každá personalizační fráze musí být v jádru právě jednou; jinak by personalizace tiše
        zmizela (a agent by dostal pokyn eskalovat sám na sebe).
    """
    joined = "\n".join(core)
    for sysid, pairs in PERSONALIZATION.items():
        for phrase, _replacement in pairs:
            found = joined.count(phrase)
            if found != 1:
                raise ValueError(
                    f"prompt core tailoring for '{sysid}': phrase \"{phrase}\" must occur exactly once between "
                    f"JADRO-START and JADRO-END of agenti-a-prompty/{CORE_PATH.name}, found {found}x "
                    f"(align the core wording or the table PERSONALIZATION in nastroje/sync_prompt_core.py)"
                )


def load_core(root: Path | None = None) -> list[str]:
    """Core rule lines between the markers. / Řádky pravidel mezi značkami."""
    core_path = CORE_PATH if root is None else root / "agenti-a-prompty" / CORE_PATH.name
    text = core_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.search(r"<!-- JADRO-START -->[ \t]*\n(.*?)\n[ \t]*<!-- JADRO-END -->", text, flags=re.DOTALL)
    if not match:
        raise ValueError("core markers JADRO-START / JADRO-END not found")
    lines = [line for line in match.group(1).split("\n") if line.strip()]
    if not lines or any(not line.startswith("- ") for line in lines):
        raise ValueError("every core rule must be a single line starting with '- '")
    validate_personalization(lines)
    return lines


def identity_line(agent: dict, total: int) -> str:
    quota = Decimal(str(agent["budget_usd"])) * OPERATING_QUOTA_PCT / 100
    return (
        f"- Jsi ai zaměstnanec č. {agent['id']} ({agent['sysid']}) společnosti Polarita s.r.o.; "
        f"tvůj jmenovitý měsíční podíl v rozpočtu je {agent['budget_usd']} USD, z toho provozní kvóta {OPERATING_QUOTA_PCT} % = {usd(quota)} USD "
        f"(tvrdý limit agenta; při 100 % provozní kvóty se placená volání tohoto agenta zastaví do schválení v Decisions), "
        f"{RESERVE_PCT} % jde do sdílené rezervy P1; při 100 % celofiremního stropu {total} USD se zastaví placená volání všech ai."
    )


def personalize_core(core: list[str], agent: dict) -> list[str]:
    """Prevent self-escalation loops (table PERSONALIZATION). / Zabrání smyčkám sebe-eskalace (tabulka PERSONALIZATION)."""
    pairs = PERSONALIZATION.get(agent["sysid"], [])
    out: list[str] = []
    for line in core:
        for phrase, replacement in pairs:
            line = line.replace(phrase, replacement)
        out.append(line)
    joined = "\n".join(out)
    for phrase, replacement in pairs:
        if phrase in joined or replacement not in joined:
            raise ValueError(f"card {agent['id']}: prompt core tailoring for '{agent['sysid']}' was not applied (phrase \"{phrase}\")")
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
        # EN: The core is the LAST section and consists only of "- " lines. Anything else after its heading
        #     is hand-written content that a rewrite would silently delete - stop instead.
        # CZ: Jádro je POSLEDNÍ oddíl a tvoří je jen řádky "- ". Cokoli jiného za jeho nadpisem je ručně
        #     psaný obsah, který by přepis tiše smazal - raději skonči chybou.
        foreign = [line for line in body[cut + 1:] if line.strip() and not line.startswith("- ")]
        if foreign:
            raise ValueError(
                f"card {agent['id']}: the system prompt has content after the shared core section "
                f"(\"{foreign[0][:60]}\") - move it above the core section; the core must stay last"
            )
        body = body[:cut]
    body = [line for line in body if not LEGACY_RE.match(line)]
    while body and not body[-1].strip():
        body.pop()
    numbers = [int(m.group(1)) for m in (TOP_SECTION_RE.match(line) for line in body) if m]
    personalized = personalize_core(core, agent)
    section = [f"{max(numbers, default=0) + 1}. {SECTION_TITLE}", identity_line(agent, total), *personalized]
    new_lines = lines[:start + 1] + body + [""] + section + lines[end:]
    return eol.join(new_lines)


def card_path(agent: dict, root: Path | None = None) -> Path:
    cards_dir = CARDS_DIR if root is None else root / "agenti-a-prompty"
    matches = sorted(cards_dir.glob(f"{agent['id']}-*.md"))
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
