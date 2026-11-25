"""Výkopová brána TEST. Trasa a minima pocházejí z registru projektanta, datum a archiv z databáze."""
from datetime import date
from decimal import Decimal
import re


def milimetry(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,6})?", value):
        raise ValueError("Rozměr musí být nezáporné desetinné číslo v milimetrech.")
    return Decimal(value)


def plati(record, day):
    return date.fromisoformat(record["plati_od"]) <= day <= date.fromisoformat(record["plati_do"])


def vyhodnot(stav):
    """Vrací důvody blokace. Poškozené nebo chybějící podklady nemohou uvolnit zkoušku."""
    try:
        return posud(stav)
    except (KeyError, AttributeError, ValueError, TypeError, IndexError):
        return ["Neúplná nebo neplatná data projektu, metodiky či vyjádření."]


def posud(stav):
    route, policy, docs = stav["projekt"], stav["metodika"], stav["doklady"]
    day = date.fromisoformat(stav["den"])
    revision = stav["revize"]
    if not re.fullmatch("[a-f0-9]{64}", revision) or docs["revize"] != revision:
        return ["Vyjádření patří k jiné revizi trasy."]
    if policy["ucel"] != "simulace" or not plati(policy, day):
        return ["Pro den zkoušky chybí platná testovací metodika."]
    owners, points, sections = route["spravci"], route["body_mm"], route["useky"]
    if (route["hladina"] != "EL_VYKOPY_DTM_SITE" or not isinstance(owners, list) or not owners
            or any(not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,63}", name) for name in owners)
            or len(set(owners)) != len(owners)):
        return ["Projekt nemá úplný soupis správců na hladině DTM."]
    if (not isinstance(points, list) or len(points) < 2
            or any(not isinstance(p, list) or len(p) != 2 or any(type(n) is not int for n in p) for p in points)
            or any(a == b for a, b in zip(points, points[1:]))):
        return ["Neplatná geometrie zemní trasy."]
    archive = stav["archiv"]
    reasons = []
    if docs["mapa"] not in archive:
        reasons.append("Ve spisu chybí archivovaný soupis dotčených sítí.")
    used = {docs["mapa"]}
    for owner in owners:
        statement = docs["vyjadreni"].get(owner)
        if (not statement or statement["revize"] != revision or statement["souhlas"] is not True
                or not plati(statement, day) or statement["sha256"] not in archive
                or statement["sha256"] in used):
            reasons.append(f"{owner} · chybí platné souhlasné vyjádření pro tuto trasu ve spisu.")
        else:
            used.add(statement["sha256"])
    covered = set()
    minimum_cover = milimetry(policy["kryti_mm"])
    for section in sections:
        start, end = section["od"], section["do"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end < len(points) or end != start + 1:
            return ["Měření neodpovídá úseku mezi sousedními body trasy."]
        covered.add(start)
        kind = section["stret"]
        if section["spravce"] not in owners or kind not in ("krizeni", "soubeh", "bez-stretu"):
            return ["V úseku je neznámý správce nebo neurčený způsob dotčení sítě."]
        if milimetry(section["kryti_mm"]) < minimum_cover:
            reasons.append(f"Úsek {start + 1} · nedostatečné krytí.")
        if kind != "bez-stretu" and milimetry(section["odstup_mm"]) < milimetry(policy["odstup_mm"][kind]):
            reasons.append(f"Úsek {start + 1} · nedostatečný odstup ({kind}).")
    if covered != set(range(len(points) - 1)):
        reasons.append("Chybí měření na některém úseku trasy.")
    return reasons
