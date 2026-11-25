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
        karta = json.loads(call("GET", api + "/" + kod))
        riziko = karta["lps"]
        ocekavane = ("0.0004", "0.000104", True) if varianta == "kladny" else ("0.001", "0.00026", False)
        if (len(riziko["slozky"]) != 4 or riziko["mez"] != "0.0002"
                or (riziko["pred"], riziko["po"], riziko["po_v_mezi"]) != ocekavane):
            raise ValueError("Spis má nesprávný rozklad nebo celkový výsledek rizika LPS.")
        print(kod, riziko["metodika"], riziko["pred"], "→", riziko["po"], flush=True)
        model = karta["bilance_EV"]
        vedeni = karta["vedeni"]
        kandidat = vedeni["varianty"][1]
        vyber, ubytek, poruchy = ("2.5", "6", []) if varianta == "kladny" else (
            None, "54", ["ubytek", "porucha_L_PE", "zkrat_L_N"])
        if (vedeni["vybrany_mm2"] != vyber or kandidat["prurez_mm2"] != "2.5"
                or kandidat["dU_V"] != ubytek or kandidat["chyby"] != poruchy):
            raise ValueError("Spis má nesprávný výsledek kontroly vedení.")
        print(kod, vedeni["metodika"], "·", vedeni["varianty"], flush=True)
        if (model["metodika"] != "SIM-DLM-01/1" or model["soudoby_prikon_W"] != prikon
                or [model["faze"][f]["prideleno_EV_A"] for f in ("L1","L2","L3")] != proudy
                or model["pretizene_faze"] != pretizeni):
            raise ValueError("Nesouhlasí fáze, příkon, metodika nebo vyhodnocení přetížení.")
        print(kod, prikon, "W ·", model["vozidla_A"], "A ·", model["faze"], flush=True)


if __name__ == "__main__":
    over(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
