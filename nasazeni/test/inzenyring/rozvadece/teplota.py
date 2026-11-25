"""Interpolace laboratorní křivky fiktivní skříně pro ověření softwaru."""
from datetime import date
from decimal import Decimal
import re


def cislo(text):
    if not isinstance(text, str) or not re.fullmatch(r"-?[0-9]{1,6}(?:\.[0-9]{1,4})?", text):
        raise ValueError("Očekávána konečná desetinná hodnota.")
    return Decimal(text)


def posud(metodika, osazeni, kusovnik):
    den = date.fromisoformat(osazeni["den_posouzeni"])
    if (metodika["rozsah"] != osazeni["rozsah"] or metodika["jednotky"] != ["W", "K", "K"] or
            metodika["pravidla"] != ["TEST-ZAKLAD-1", "TEST-VYKON-1", "TEST-OTEP-1"] or
            not date.fromisoformat(metodika["od"]) <= den <= date.fromisoformat(metodika["do"])):
        raise ValueError("Pro třídu, den a jednotky chybí platná zkušební metodika.")
    prvky = osazeni["pristroje"]
    oznaceni = [p["oznaceni"] for p in prvky]
    if not oznaceni or len(set(oznaceni)) != len(oznaceni) or set(oznaceni) != set(kusovnik):
        raise ValueError("Osazení neodpovídá kusovníku.")
    ztraty = [cislo(p["ztrata_W"]) for p in prvky]
    if min(ztraty) < 0:
        raise ValueError("Ztráta příkonu musí být nezáporná.")
    vykon = sum(ztraty)
    krivka = [tuple(cislo(v) for v in bod) for bod in metodika["krivka_W_K_stred_K_vrch"]]
    if (len(krivka) < 2 or krivka[0] != (0, 0, 0) or
            any(len(bod) != 3 or not 0 <= bod[1] <= bod[2] for bod in krivka) or
            any(b[0] <= a[0] or b[1] < a[1] or b[2] < a[2] for a, b in zip(krivka, krivka[1:]))):
        raise ValueError("Kalibrační křivka TEST je neplatná.")
    for dolni, horni in zip(krivka, krivka[1:]):
        if dolni[0] <= vykon <= horni[0]:
            podil = (vykon - dolni[0]) / (horni[0] - dolni[0])
            stred, vrch = (dolni[i] + podil * (horni[i] - dolni[i]) for i in (1, 2))
            break
    else:
        raise ValueError("Pro výkon mimo laboratorní křivku nelze vystavit návrh.")
    teplota = cislo(osazeni["okoli_C"]) + vrch
    mez = min(cislo(p["mez_C"]) for p in prvky)
    if teplota > mez:
        raise ValueError("Model překračuje dovolenou teplotu součástky.")
    return {k: format(v.normalize(), "f") for k, v in {
        "ztrata_W": vykon, "stred_K": stred, "vrch_K": vrch, "uvnitr_C": teplota, "mez_C": mez}.items()}
