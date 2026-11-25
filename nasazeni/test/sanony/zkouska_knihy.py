"""Ověří cestu syntetické zprávy z karantény přes archiv až do knihy objektu."""
import argparse
from datetime import datetime, date
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
from urllib.error import URLError
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from overeni import NeocekavanyStav, pripojeni, prihlasit


def over(origin, password):
    spojeni = pripojeni(origin)
    prihlasit(spojeni, password)

    def call(*args):
        try:
            return spojeni(*args)
        except NeocekavanyStav as exc:
            if exc.status != 401:
                raise
        prihlasit(spojeni, password)
        return spojeni(*args)

    api = "/lhutnik-test/api/"
    case = json.loads(call("POST", api+"spisy", json.dumps({
        "pozadavek":str(uuid5(NAMESPACE_URL, "polarita.test/spis-zkouska-revizni-knihy")), "branch_id":101
    }).encode(), "application/json"))["case_id"]
    pdf = Path(__file__).with_name("revize-vzor-test.pdf").read_bytes()
    key = str(uuid5(NAMESPACE_URL, "polarita.test/kniha/" + case + "/" + sha256(pdf).hexdigest()))
    receipt = json.loads(call("PUT", api+"sanony/"+case+"/"+key, pdf, "application/pdf"))
    if receipt["case_id"] != case or receipt["priloha"] != key or receipt["bajtu"] != len(pdf):
        raise RuntimeError("Potvrzení se liší od předané testovací zprávy.")
    print(f"Spis {case} převzal syntetickou revizní zprávu.", flush=True)
    deadline = time.monotonic() + 7200
    while receipt["stav"] == "v-karantene":
        if time.monotonic() >= deadline:
            raise TimeoutError("Archiv nepotvrdil OCR ve vyhrazeném čase.")
        time.sleep(30)
        try:
            rows = json.loads(call("GET", api+"sanony/"+case))
        except NeocekavanyStav as exc:
            if exc.status in (502, 503, 504):
                continue
            raise
        except (TimeoutError, ConnectionError, URLError):
            continue
        receipt = next(r for r in rows if r["priloha"] == key)
    if receipt["stav"] != "ocr-hotovo" or not receipt["dokument"]:
        raise RuntimeError("Syntetická revizní zpráva neprošla karanténou a OCR.")
    route = api + "kniha/" + case
    values = {"objekt":"TEST-HALA", "zarizeni":"TEST-R1", "revize":"2026-01-10",
              "upozornit":"2026-11-01", "platnost":"2026-12-31", "priloha":key}
    for _ in range(2):
        response = json.loads(call("POST", route, json.dumps(values).encode(), "application/json"))
        if response != {"stav":"ulozeno"}:
            raise RuntimeError("Kniha nepotvrdila zápis.")
    rows = [r for r in json.loads(call("GET", route)) if (r["objekt"],r["zarizeni"]) == ("TEST-HALA","TEST-R1")]
    if len(rows) != 1 or any(rows[0][k] != v for k,v in values.items()) or rows[0]["dokument"] != receipt["dokument"]:
        raise RuntimeError("Kniha nevrátila jeden zápis se zdrojovým dokumentem.")
    today = datetime.now(ZoneInfo("Europe/Prague")).date()
    state = "po-lhute" if today > date.fromisoformat(values["platnost"]) else (
        "blizi-se" if today >= date.fromisoformat(values["upozornit"]) else "ve-lhute")
    if rows[0]["stav"] != state:
        raise RuntimeError("Stav neodpovídá termínům testovací zprávy.")
    print(f"Dokument {receipt['dokument']} ze spisu {case} prošel karanténou a OCR. "
          f"Kniha po opakovaném zápisu vrací jeden záznam TEST-HALA / TEST-R1 se stavem {state}.")
    job = uuid5(NAMESPACE_URL, "polarita.test/sanony/" + key).hex + ".pdf"
    return case, receipt["dokument"], job


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--doklad", type=Path)
    args = parser.parse_args()
    case, document, job = over(args.origin, sys.stdin.readline().rstrip("\r\n"))
    if args.doklad:
        args.doklad.write_text(f"{case} {document} {job}\n", encoding="ascii")
