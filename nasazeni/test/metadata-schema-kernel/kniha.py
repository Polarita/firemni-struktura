"""Kontrolované termíny v interní digitální knize objektu TEST."""
from datetime import date
import re

from zaznamy import Problem, identifier, query


def oznaceni(kod):
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", kod):
        raise Problem(400, "Neplatné číslo spisu.")
    return kod


def prehled(data, kod):
    rows = query(data, """
        SELECT coalesce((SELECT jsonb_agg(to_jsonb(r) ORDER BY objekt,zarizeni)
            FROM polarita_test_spisy.kniha_objektu r WHERE r.case_id=k.case_id),'[]'::jsonb)
        FROM polarita_test_spisy.karty k WHERE k.case_id=:'kod';""", kod=oznaceni(kod))
    if rows is None:
        raise Problem(404, "Spis nebyl nalezen.")
    return rows


def zaznam(data, kod, body):
    fields = {"objekt","zarizeni","priloha","revize","upozornit","platnost"}
    if not isinstance(body, dict) or body.keys() != fields or not all(isinstance(v, str) for v in body.values()):
        raise Problem(400, "Vyplňte zařízení, doklad i všechny termíny.")
    for key in ("objekt", "zarizeni"):
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,47}", body[key]):
            raise Problem(400, "Označení může obsahovat velká písmena A–Z, číslice, pomlčku a podtržítko.")
    for key in ("revize", "upozornit", "platnost"):
        try:
            if date.fromisoformat(body[key]).isoformat() != body[key]:
                raise ValueError
        except ValueError:
            raise Problem(400, "Zadejte platná data.") from None
    identifier(body["priloha"])
    result = query(data, """SELECT to_jsonb(polarita_test_spisy.zapis_revizi(:'kod',:'objekt',:'zarizeni',
        :'priloha'::uuid,:'revize'::date,:'upozornit'::date,:'platnost'::date));""", kod=oznaceni(kod), **body)
    if result == "datum":
        raise Problem(400, "Zkontrolujte datum uskutečněné revize, připomenutí a konce platnosti.")
    if result == "doklad":
        raise Problem(409, "Vyberte archivovaný doklad z tohoto spisu.")
    if result == "kolize":
        raise Problem(409, "Pro stejné zařízení a den je už zapsána jiná revize.")
    if result != "ulozeno":
        raise RuntimeError("Databáze nepotvrdila zápis.")
    return {"stav": result}
