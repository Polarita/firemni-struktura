"""Bilance činného příkonu a nabíjecích proudů ve fiktivním odporovém modelu TEST."""
from decimal import Decimal
import re

from metodiky import hodnota, nacti, platna, text


FAZE = ("L1", "L2", "L3")


def proud(cislo):
    if type(cislo) is not int or not 1 <= cislo <= 128:
        raise ValueError("Proud mimo celoampérový rozsah simulátoru.")
    return cislo


def fazovy_vektor(vstup):
    if not isinstance(vstup, dict) or set(vstup) != set(FAZE):
        raise ValueError("Projekt musí mít samostatný údaj pro každou fázi.")
    return {f: hodnota(vstup[f]) for f in FAZE}


def bilance(projekt, metodiky):
    metoda = platna(projekt, metodiky, "odporovy-trojfazovy")
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
    return {"metodika": metoda["kod"], "den": projekt["den"], "pretizene_faze": pretizene,
            "soudoby_prikon_W": text(sum(prikon.values())), "vozidla_A": alokace,
            "faze": {f: {"soudoby_prikon_W": text(prikon[f]), "rezerva_po_EV_W": text(rezerva[f]),
                         "prideleno_EV_A": sum(alokace[v["id"]] for v in vozidla if f in v["faze"])}
                     for f in FAZE}}


def pro_spis(pozadavek):
    projekty = nacti("dlm-projekty-test.json")
    if pozadavek in projekty:
        return bilance(projekty[pozadavek], nacti("dlm-metodiky-test.json"))
    return None
