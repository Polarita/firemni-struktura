"""Připraví data pro Typst pouze pro úplný testovací případ."""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

from import_mereni import LIMIT, nacti, unikat
from posouzeni import dukazy, posud, vyhodnot


def priprav(src, plan, case, now, *, pas=None):
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case):
        raise ValueError("Neplatný spis.")
    with src.open("rb") as f:
        raw = f.read(LIMIT+1)
    rows = nacti(raw, src.suffix.removeprefix("."))
    model = json.loads(plan.read_bytes(), object_pairs_hook=unikat)
    hashes = dict(model["otisky_dokladu"])
    if pas is None:
        result = vyhodnot(model, plan.parent / "doklady", rows, now)
        if result["stav"] == "FAIL_CLOSED":
            raise ValueError(result["duvod"])
        result["puvod_podkladu"] = "mistni-vzor"
    else:
        if pas["case_id"] != case or pas["stav"] != "navrh-test" or pas["predani_do_provozu"] is not False:
            raise ValueError("Pro zkoušený spis chybí vydaný modelový pas.")
        ids = {kind:model["prilohy"][kind] for kind in ("pas", "stitek")}
        for doc_id in ids.values():
            del hashes[doc_id]
        docs = dukazy(plan.parent / "doklady", hashes)
        for kind, doc_id in ids.items():
            docs[doc_id] = {"id":doc_id, "druh":kind, "projekt":model["projekt"], "uzavren":True, "den":pas["den"]}
            hashes[doc_id] = pas["pdf_sha256"]
        result = posud(model, docs, rows, now)
        result["pas"] = pas
        result["puvod_podkladu"] = "vydany-pas-ve-spisu"
    return dict(result, spis=case, vstup_sha256=hashlib.sha256(raw).hexdigest(), doklady_sha256=hashes)



if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("vstup", type=Path)
    cli.add_argument("--plan", required=True, type=Path)
    cli.add_argument("--spis", required=True)
    args = cli.parse_args()
    try:
        result = priprav(args.vstup, args.plan, args.spis, date.today())
    except (ValueError, OSError, csv.Error) as err:
        sys.exit(f"FAIL_CLOSED · {err}")
    print(json.dumps(result, ensure_ascii=False))
