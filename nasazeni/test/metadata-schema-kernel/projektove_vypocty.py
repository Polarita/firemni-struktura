"""Sestavení projektové části karty ze stejného ověřeného vydání báze."""
import dlm
import lps
import vedeni
from metodiky import nacti
from registr_metodik import nacti_bazi


def cast_karty(pozadavek):
    modely = (("dlm","bilance_EV",dlm.bilance), ("vedeni","vedeni",vedeni.posud), ("lps","lps",lps.posud))
    projekty = []
    for skupina, klic, posud in modely:
        projekt = nacti(skupina + "-projekty-test.json").get(pozadavek)
        if projekt is not None:
            projekty.append((skupina, klic, posud, projekt))
    if not projekty:
        return {}
    try:
        registr, podklady = nacti_bazi()
        vysledky = {}
        for skupina, klic, posud, projekt in projekty:
            vysledek = posud(projekt, registr[skupina])
            vysledky[klic] = {**vysledek, "zdroj_metodiky":podklady[vysledek["metodika"]]}
        return vysledky
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        return {"chyba_metodik":"Výpočty jsou pozastavené. Ověření metodiky ve firemní bázi se nezdařilo."}
