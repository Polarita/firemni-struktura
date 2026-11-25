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
from posouzeni import vyhodnot


def priprav(src, plan, case, now):
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case):
        raise ValueError("Neplatný spis.")
    with src.open("rb") as f:
        raw = f.read(LIMIT+1)
    rows = nacti(raw, src.suffix.removeprefix("."))
    model = json.loads(plan.read_bytes(), object_pairs_hook=unikat)
    result = vyhodnot(model, plan.parent / "doklady", rows, now)
    if result["stav"] == "FAIL_CLOSED":
        raise ValueError(result["duvod"])
    return dict(result, spis=case, vstup_sha256=hashlib.sha256(raw).hexdigest(),
                doklady_sha256=model["otisky_dokladu"])


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
