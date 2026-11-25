"""Vyhodnocení cvičných měření z oddělené metodiky a ověřených dokladů."""
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import re

from import_mereni import unikat


def den(text):
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise ValueError("Neplatné datum měření nebo dokladu.")
    return date.fromisoformat(text)


def cislo(text):
    if not isinstance(text, str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,9})?", text):
        raise ValueError("Neplatná číselná hodnota.")
    return Decimal(text)


def dukazy(directory, registry):
    found = {}
    for key, digest in registry.items():
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,63}", key) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Chybná identifikace dokladu.")
        raw = (directory / (key + ".json")).read_bytes()
        if len(raw) > 65536 or sha256(raw).hexdigest() != digest:
            raise ValueError("Otisk dokladu nesouhlasí: " + key)
        doc = json.loads(raw, object_pairs_hook=unikat)
        if doc["id"] != key or doc["rezim"] != "TEST":
            raise ValueError("Obsah dokladu neodpovídá registru.")
        found[key] = doc
    return found


def posud(plan, docs, rows, dnes):
    if plan["rezim"] != "TEST" or not rows:
        raise ValueError("Vyžadován testovací projekt a úplná měření.")
    project = plan["projekt"]
    day = den(plan["den"])
    if day > dnes or not (den(plan["metodika"]["od"]) <= day <= den(plan["metodika"]["do"])):
        raise ValueError("Pro den měření chybí platná testovací metodika.")
    expected = plan["body"]
    if not isinstance(expected, dict) or not expected or len(expected) != len(rows):
        raise ValueError("Počet výsledků neodpovídá měřicímu plánu.")
    for flag, kinds in (("novy_rozvadec", ("pas", "stitek")), ("stavebni_denik", ("uzavreny-denik",)),
                        ("vykop", ("vytyceni",))):
        if type(plan[flag]) is not bool:
            raise ValueError("Neúplné údaje o požadovaných dokumentech.")
        if plan[flag]:
            for kind in kinds:
                doc = docs[plan["prilohy"][kind]]
                if doc["druh"] != kind or doc["projekt"] != project or doc["uzavren"] is not True or den(doc["den"]) > day:
                    raise ValueError("Chybí odpovídající uzavřený doklad: " + kind)
    checked = {}
    for row in rows:
        key = row["bod"]
        if key in checked or key not in expected or row["projekt"] != project or den(row["den"]) != day:
            raise ValueError("Měření se opakuje nebo patří k jinému projektu, bodu či dni.")
        spec = expected[key]
        serial = row["pristroj"]
        cal = docs[plan["kalibrace"][serial]]
        if (cal["druh"] != "kalibrace" or cal["pristroj"] != serial or spec["velicina"] not in cal["veliciny"]
                or not den(cal["od"]) <= day <= den(cal["do"])):
            raise ValueError("Chybí platná kalibrace použitého měřidla.")
        rule = plan["metodika"]["pravidla"][spec["velicina"]]
        if rule["jednotka"] != row["jednotka"] or rule["porovnani"] not in ("max", "min"):
            raise ValueError("Nesouhlasí jednotka nebo metodika vyhodnocení.")
        value, limit = cislo(row["hodnota"]), cislo(rule["mez"])
        ok = value <= limit if rule["porovnani"] == "max" else value >= limit
        checked[key] = dict(row, vyhovel=ok, obvod=spec["obvod"], ustanoveni=rule["ustanoveni"],
                            porovnani=rule["porovnani"], mez=rule["mez"], kalibracni_list=cal["id"],
                            navrh_lhuty=rule["navrh_lhuty"] if not ok else None)
    failed = sorted(k for k, row in checked.items() if not row["vyhovel"])
    return {"rezim": "TEST", "stav": "navrh-zaporny" if failed else "navrh-kladny",
            "projekt": project, "den": day.isoformat(), "metodika": plan["metodika"]["id"],
            "vysledky": [checked[k] for k in sorted(checked)], "zavady": failed,
            "podpis": "ceka-na-revizniho-technika", "predani_do_provozu": False}


def vyhodnot(plan, directory, rows, dnes):
    try:
        docs = dukazy(directory, plan["otisky_dokladu"])
        return posud(plan, docs, rows, dnes)
    except (KeyError, OSError, TypeError, ValueError) as error:
        return {"rezim": "TEST", "stav": "FAIL_CLOSED", "duvod": str(error), "predani_do_provozu": False}
