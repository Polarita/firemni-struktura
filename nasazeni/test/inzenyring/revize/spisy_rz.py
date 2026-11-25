"""Založení a kontrola testovacích revizních spisů přes přihlášené ředitelství."""
import hashlib
import json
import re
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5
from urllib.parse import urlsplit

VARIANTY = ("kladny", "zaporny")


def id_spisu(varianta):
    if varianta not in VARIANTY:
        raise ValueError("Neznámá zkouška.")
    return uuid5(NAMESPACE_URL, "polarita.test/inzenyring/revize/" + varianta)


def over(origin, password, kontrola):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanony"))
    from overeni import pripojeni, prihlasit
    call = pripojeni(origin)
    prihlasit(call, password)
    serials = set()
    for varianta in VARIANTY:
        body = json.dumps({"pozadavek":str(id_spisu(varianta)), "branch_id":101}).encode()
        case = json.loads(call("POST","/lhutnik-test/api/spisy",body,"application/json"))["case_id"]
        if kontrola:
            karta = json.loads(call("GET", "/lhutnik-test/api/spisy/"+case))
            info = karta["revizni_navrh"]
            [panel] = [r for r in karta["rozvadece"] if r["oznaceni"] == "RP1"]
            serial = panel["vyrobni_cislo"]
            if not re.fullmatch(r"RZ-[0-9]{4}-[0-9]{5}", serial) or serial in serials:
                raise ValueError("Karta nemá vlastní platné výrobní číslo rozváděče.")
            rev = info["vydani_pasu"]
            if not re.fullmatch(r"[a-f0-9]{64}", rev):
                raise ValueError("Revize nemá platné vydání pasu.")
            podklad = call("GET", f"/lhutnik-test/api/pasy/{case}/{serial}/{rev}/vyrobni-pas.pdf")
            if info["vyrobni_cislo"] != serial or info["pas_sha256"] != hashlib.sha256(podklad).hexdigest():
                raise ValueError("Revizní návrh odkazuje na jiné vydání výrobního pasu.")
            serials.add(serial)
            pdf = call("GET", "/lhutnik-test/api/revize/"+case+"/navrh.pdf")
            if (not pdf.startswith(b"%PDF-") or hashlib.sha256(pdf).hexdigest() != info["pdf_sha256"]
                    or info["stav"] != "navrh-"+varianta or info["predani_do_provozu"] is not False
                    or urlsplit(info["rozhodnuti"]).netloc != urlsplit(origin).hostname+":8445"):
                raise ValueError("Portál vrátil nesprávný doklad nebo rozhodnutí.")
            print(case, serial, info["stav"], "SHA-256", info["pdf_sha256"], "·", info["rozhodnuti"], flush=True)
        else:
            print(case, varianta, flush=True)


if __name__ == "__main__":
    import argparse
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("origin")
    cli.add_argument("--over", action="store_true")
    args = cli.parse_args()
    over(args.origin, sys.stdin.readline().rstrip("\r\n"), args.over)
