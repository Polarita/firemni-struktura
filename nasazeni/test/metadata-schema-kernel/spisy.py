"""Trvalá řada spisů TEST sdílená centrálou a pobočkami."""
import re
from zaznamy import identifier, Problem, query


def zaloz(data, body):
    if not isinstance(body, dict) or body.keys() != {"pozadavek", "branch_id"} or type(body["branch_id"]) is not int:
        raise Problem(400, "Zadejte identifikátor požadavku a číslo pobočky.")
    if not 101 <= body["branch_id"] <= 999:
        raise Problem(400, "Číslo pobočky je mimo rozsah.")
    karta = query(data, "SELECT polarita_test_spisy.zaloz(:'id'::uuid, :'branch'::integer);",
                  id=identifier(body["pozadavek"]), branch=str(body["branch_id"]))
    if "chyba" in karta:
        if karta["chyba"] == "pobocka":
            raise Problem(400, "Pobočka není v registru.")
        raise Problem(409, "Identifikátor požadavku je již použitý nebo je roční řada vyčerpaná.")
    return karta


def najdi(data, oznaceni):
    if not isinstance(oznaceni, str) or not re.fullmatch(r"POL-(?:[1-9][0-9]{2}-)?[0-9]{4}-[0-9]{5}", oznaceni):
        raise Problem(400, "Neplatné označení spisu.")
    karta = query(data, "SELECT to_jsonb(k) FROM polarita_test_spisy.karty k WHERE k.case_id=:'key' OR k.alias=:'key';",
                  key=oznaceni)
    if karta is None:
        raise Problem(404, "Spis nebyl nalezen.")
    return karta
