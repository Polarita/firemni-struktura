"""Kontrola vydaných pasů přes stejné přihlášení jako v ředitelství."""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1] / "sanony"))
sys.path.insert(0,str(HERE.parent / "revize"))
from overeni import prihlasit, pripojeni
from spisy_rz import VARIANTY, id_spisu


def over(origin, heslo):
    api = "/lhutnik-test/api/"
    call = pripojeni(origin)
    prihlasit(call, heslo)
    docs = []
    for variant in VARIANTY:
        body = json.dumps({"pozadavek":str(id_spisu(variant)), "branch_id":101}).encode()
        case = json.loads(call("POST",api+"spisy",body,"application/json"))["case_id"]
        karta = json.loads(call("GET",api+"spisy/"+case))
        [panel] = [p for p in karta["rozvadece"] if p["oznaceni"] == "RP1"]
        serial = panel["vyrobni_cislo"]
        info = panel["pas"]
        if not re.fullmatch(r"RZ-[0-9]{4}-[0-9]{5}", serial) or info != {
                "case_id":case, "vyrobni_cislo":serial, "strany":5, "pdf_sha256":info["pdf_sha256"],
                "kniha":origin+"/lhutnik-test/spisy?spis="+case+"&oddil=kniha",
                "stav":"navrh-test","predani_do_provozu":False}:
            raise ValueError("Karta odkazuje na nesprávný pas.")
        path = api+"pasy/"+case+"/"+serial+"/vyrobni-pas.pdf"
        raw = call("GET", path)
        if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != info["pdf_sha256"]:
            raise ValueError("Dodané PDF nesouhlasí s vydáním pasu.")
        docs.append((case, serial))
        print(case, serial, info["pdf_sha256"], "· 5 stran ·", info["kniha"], flush=True)
    call("GET", api+"pasy/"+docs[0][0]+"/"+docs[1][1]+"/vyrobni-pas.pdf", status=404)


if __name__ == "__main__":
    over(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
