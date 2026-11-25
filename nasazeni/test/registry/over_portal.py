"""Porovnání čísel a zdrojových otisků se skutečnými kartami spisů ve VPN."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"sanony"))
from overeni import pripojeni, prihlasit


def over(origin, heslo, protokol):
    ocekavane = {}
    for radek in protokol.splitlines():
        shoda = re.fullmatch(r"(POL-[0-9]{4}-[0-9]{5}) ((?:FAK|ORG-UOL|VYD)-[0-9]{4}-[0-9]{5}) ([a-f0-9]{64})", radek)
        if shoda:
            spis,cislo,otisk = shoda.groups()
            ocekavane.setdefault(spis,{})[cislo] = otisk
    if len(ocekavane) != 2 or any(len(sada) != 3 for sada in ocekavane.values()):
        raise ValueError("Chybí doklady očekávané ve dvou testovacích spisech.")
    call = pripojeni(origin)
    prihlasit(call,heslo)
    for spis, doklady in ocekavane.items():
        karta = json.loads(call("GET", "/lhutnik-test/api/spisy/"+spis))
        skutecne = {r["cislo"]:r["podklad_sha256"] for r in karta["doklady_registru"]}
        cizi = set().union(*(s.keys() for k,s in ocekavane.items() if k != spis))
        if not doklady.items() <= skutecne.items() or cizi & skutecne.keys():
            raise ValueError("Karta vrátila nesprávné doklady nebo otisky.")
        print(spis, "· účet správce ověřil", ", ".join(sorted(doklady)))


if __name__ == "__main__":
    over(sys.argv[1],sys.stdin.readline().rstrip("\r\n"),Path(sys.argv[2]).read_text())
