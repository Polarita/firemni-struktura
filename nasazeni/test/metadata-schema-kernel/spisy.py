"""Trvalá řada spisů TEST sdílená centrálou a pobočkami."""
import re
from zaznamy import identifier, Problem, query


def zaloz(data, body):
    if not isinstance(body, dict) or body.keys() != {"pozadavek", "branch_id"} or type(body["branch_id"]) is not int:
        raise Problem(400, "Zadejte identifikátor požadavku a číslo pobočky.")
    if not 101 <= body["branch_id"] <= 999:
        raise Problem(400, "Číslo pobočky je mimo rozsah.")
    karta = query(data, "SELECT polarita_registr_test.zaloz_spis(:'id'::uuid, :'branch'::integer);",
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


def prevzate_sanony(data, kod):
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", kod):
        raise Problem(400, "Neplatné číslo spisu.")
    return query(data, """
        SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.prijato DESC,p.priloha), '[]'::jsonb)
        FROM (SELECT * FROM polarita_test_spisy.potvrzeni_sanonu WHERE case_id=:'kod'
              ORDER BY prijato DESC,priloha LIMIT 50) p;""", kod=kod)


def casova_osa(data, kod, pred=None):
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", kod):
        raise Problem(400, "Neplatné hlavní číslo spisu.")
    if pred is not None and not re.fullmatch(r"[0-9]{20}\.[1-4][.A-Za-z0-9_-]{0,115}", pred):
        raise Problem(400, "Neplatná pozice na časové ose.")
    page = query(data, """
        SELECT coalesce((
            SELECT jsonb_agg(to_jsonb(u) ORDER BY pozice DESC)
            FROM (SELECT cas,druh,popis,dokument,pozice FROM polarita_test_spisy.casova_osa
                  WHERE case_id=k.case_id AND (:'pred'='' OR pozice < :'pred')
                  ORDER BY pozice DESC LIMIT 21) u
        ),'[]'::jsonb) FROM polarita_test_spisy.karty k WHERE k.case_id=:'kod';""",
                 kod=kod, pred=pred or "")
    if page is None:
        raise Problem(404, "Spis nebyl nalezen.")
    return {"udalosti": page[:20], "dalsi": page[19]["pozice"] if len(page) > 20 else None}
