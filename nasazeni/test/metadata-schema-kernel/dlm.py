"""Bilance činného příkonu a nabíjecích proudů ve fiktivním odporovém modelu TEST."""
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re


FAZE = ("L1", "L2", "L3")
SOUBORY = Path(__file__).resolve().parent


def hodnota(text):
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,6})(?:\.[0-9]{1,4})?", text):
        raise ValueError("Očekávána konečná nezáporná desetinná hodnota.")
    return Decimal(text)


def proud(cislo):
    if type(cislo) is not int or not 1 <= cislo <= 128:
        raise ValueError("Proud mimo celoampérový rozsah simulátoru.")
    return cislo


def fazovy_vektor(vstup):
    if not isinstance(vstup, dict) or set(vstup) != set(FAZE):
        raise ValueError("Projekt musí mít samostatný údaj pro každou fázi.")
    return {f: hodnota(vstup[f]) for f in FAZE}


def text(hodnota):
    return format(hodnota.normalize(), "f")


def bilance(projekt, metodiky):
    den = date.fromisoformat(projekt["den"])
    metody = [m for m in metodiky if m["ucel"] == projekt["ucel"] == "simulace"
              and m["model"] == projekt["model"] == "odporovy-trojfazovy"
              and date.fromisoformat(m["od"]) <= den <= date.fromisoformat(m["do"])]
    if len(metody) != 1:
        raise ValueError("Pro datum a model chybí jednoznačná metodika TEST.")
    metoda = metody[0]
    napeti = hodnota(projekt["fazove_napeti_V"])
    limity = fazovy_vektor(projekt["limit_A"])
    minimum = proud(metoda["minimum_EV_A"])
    if not napeti or not min(limity.values()) or not projekt["skupiny"]:
        raise ValueError("Chybí napětí, kapacita přívodu nebo popis spotřeby.")
    prikon = dict.fromkeys(FAZE, Decimal(0))
    for skupina in projekt["skupiny"]:
        soucinitel = hodnota(metoda["soudobost"][skupina["druh"]])
        if soucinitel > 1:
            raise ValueError("Neplatný součinitel soudobosti.")
        for f, watty in fazovy_vektor(skupina["instalovano_W"]).items():
            prikon[f] += watty * soucinitel

    # Do porovnání s limitem vstupují přesné watty, bez zaokrouhlení podílu P/U.
    rezerva = {f: limity[f] * napeti - prikon[f] for f in FAZE}
    pretizene = [f for f in FAZE if rezerva[f] < 0]
    vozidla = projekt["vozidla"]
    if not isinstance(vozidla, list) or len(vozidla) > 32:
        raise ValueError("Neplatná skupina vozidel.")
    alokace = {}
    for v in vozidla:
        jmeno, faze = v["id"], v["faze"]
        if (not re.fullmatch(r"[A-Z0-9-]{1,32}", jmeno) or jmeno in alokace
                or not isinstance(faze, list) or not faze or len(faze) != len(set(faze))
                or not set(faze) <= set(FAZE) or proud(v["pozadavek_A"]) < minimum):
            raise ValueError("Neplatná identita, zapojení nebo požadavek vozidla.")
        alokace[jmeno] = 0
    if not pretizene:
        # Pořadí ve vstupu určuje přednost přijetí. Po přijetí střídat po jednom A.
        for v in vozidla:
            if all(rezerva[f] >= minimum * napeti for f in v["faze"]):
                alokace[v["id"]] = minimum
                for f in v["faze"]:
                    rezerva[f] -= minimum * napeti
        while True:
            zvyseno = False
            for v in vozidla:
                if (0 < alokace[v["id"]] < v["pozadavek_A"]
                        and all(rezerva[f] >= napeti for f in v["faze"])):
                    alokace[v["id"]] += 1
                    for f in v["faze"]:
                        rezerva[f] -= napeti
                    zvyseno = True
            if not zvyseno:
                break
    return {"metodika": metoda["kod"], "den": den.isoformat(), "pretizene_faze": pretizene,
            "soudoby_prikon_W": text(sum(prikon.values())), "vozidla_A": alokace,
            "faze": {f: {"soudoby_prikon_W": text(prikon[f]), "rezerva_po_EV_W": text(rezerva[f]),
                         "prideleno_EV_A": sum(alokace[v["id"]] for v in vozidla if f in v["faze"])}
                     for f in FAZE}}


def pro_spis(pozadavek):
    projekty = json.loads((SOUBORY / "dlm-projekty-test.json").read_bytes())
    if pozadavek in projekty:
        return bilance(projekty[pozadavek], json.loads((SOUBORY / "dlm-metodiky-test.json").read_bytes()))
    return None
