"""Ověření modelové bilance dvou skutečných karet přes přihlášené ředitelství."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "sanony"))
sys.path.insert(0, str(HERE / "revize"))
from overeni import prihlasit, pripojeni
from spisy_rz import id_spisu


def over(origin, heslo):
    call = pripojeni(origin)
    prihlasit(call, heslo)
    api = "/lhutnik-test/api/spisy"
    for varianta, prikon, proudy, pretizeni in (
            ("kladny", "9200", [18, 9, 9], []), ("zaporny", "11960.01", [0, 0, 0], ["L2"])):
        telo = json.dumps({"pozadavek": str(id_spisu(varianta)), "branch_id": 101}).encode()
        kod = json.loads(call("POST", api, telo, "application/json"))["case_id"]
        model = json.loads(call("GET", api + "/" + kod))["bilance_EV"]
        if (model["metodika"] != "SIM-DLM-01/1" or model["soudoby_prikon_W"] != prikon
                or [model["faze"][f]["prideleno_EV_A"] for f in ("L1","L2","L3")] != proudy
                or model["pretizene_faze"] != pretizeni):
            raise ValueError("Nesouhlasí fáze, příkon, metodika nebo vyhodnocení přetížení.")
        print(kod, prikon, "W ·", model["vozidla_A"], "A ·", model["faze"], flush=True)


if __name__ == "__main__":
    over(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
