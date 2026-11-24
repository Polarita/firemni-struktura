"""Vykreslí oficiální soupis pozic a úplné instrukce z ověřené revize Gitey pro inicializaci Paperclipu."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from zdroj_pozic import nacti

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nastroje"))
from sync_prompt_core import CHAPTER4_RE, OPERATING_QUOTA_PCT, card_path


def organization(root, source):
    canon = json.loads((root / "nastroje/kanon.json").read_bytes())
    common = (root / "agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md").read_bytes().decode("utf-8")
    charters = {}
    for department in {a["department"] for a in canon["agents"]}:
        charter, = (root / "oddeleni").glob(f"{department}-*.md")
        charters[department] = charter.read_bytes().decode("utf-8")
    channels = {name[1:3]: name[1:] for name in canon["zulip_channels"]}
    agents = []
    for agent in canon["agents"]:
        card = card_path(agent, root).read_bytes().decode("utf-8")
        match = re.search(r"^\| \*\*Přímý nadřízený\*\* \| ([^\n]+)", card, re.M)
        expected_manager = "1001" if agent["sysid"] == "ceo" else "11001"
        if not match or f"`{expected_manager}`" not in match[1]:
            raise ValueError("Nejasná hierarchie pozice " + agent["id"])
        lines = card.splitlines(keepends=True)
        chapter = next(i for i, line in enumerate(lines) if CHAPTER4_RE.match(line))
        end = next((i for i in range(chapter + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        section = "".join(lines[chapter:end])
        blocks = re.findall(r"^```text\n(.*?)^```\s*$", section, re.M | re.S)
        if len(blocks) != 1 or agent["id"] not in blocks[0]:
            raise ValueError("Nejednoznačný systémový prompt " + agent["id"])
        prompt = "\n\n".join((common, charters[agent["department"]], card))
        nominal = agent["budget_usd"] * 100
        operating, remainder = divmod(nominal * OPERATING_QUOTA_PCT, 100)
        if remainder:
            raise ValueError("Provozní podíl nelze přesně vyjádřit v centech")
        agents.append({
            "id": agent["id"], "sysid": agent["sysid"], "name": agent["name"],
            "reports_to": expected_manager, "channel": channels[agent["department"]],
            "nominal_cents": nominal, "operating_cents": operating, "reserve_cents": nominal - operating,
            "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        })
    nominal = sum(a["nominal_cents"] for a in agents)
    operating = sum(a["operating_cents"] for a in agents)
    if (len({a["id"] for a in agents}), len(channels), nominal, operating, nominal - operating) != (20, 8, 47000, 39950, 7050):
        raise ValueError("Rozpis pozic a měsíčních rozpočtů nesouhlasí s TEST přejímkou")
    return {"zdroj_gitea": source, "company": canon["company"]["name"], "branch": canon["company"]["branch"],
            "budget_cents": nominal, "reserve_cents": nominal - operating, "agents": agents}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revize", type=Path, help="Soubor revize-ci.json úspěšně ověřeného stromu")
    args = parser.parse_args()
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = nacti(args.revize, root)
        data = organization(root, source)
    json.dump(data, sys.stdout, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
