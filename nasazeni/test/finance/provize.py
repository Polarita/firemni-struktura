"""Položky provizního ledgeru z potvrzených realizací a plateb spárovaných UOL."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

HALER = Decimal("0.01")


def cislo(hodnota):
    if not isinstance(hodnota, str):
        raise ValueError("Účetní hodnota musí být desetinné číslo zapsané jako text.")
    vysledek = Decimal(hodnota)
    if not vysledek.is_finite() or vysledek != vysledek.quantize(HALER):
        raise ValueError("Chybná přesnost účetní hodnoty.")
    return vysledek


def polozka(druh, zdroj, udalost, doklad, partner, obdobi, zaklad, sazba):
    if not all(isinstance(x, str) and x.strip() for x in (zdroj, udalost, doklad, partner)):
        raise ValueError("Chybí identita zdroje, dokladu nebo partnera.")
    mesic = date.fromisoformat(obdobi)
    if mesic.day != 1:
        raise ValueError("Účetní období musí začínat prvního dne měsíce.")
    castka = (zaklad * sazba / 100).quantize(HALER, rounding=ROUND_HALF_UP)
    return dict(druh=druh, zdroj=zdroj, udalost=udalost, doklad=doklad, partner=partner,
                obdobi=mesic.isoformat(), zaklad=str(zaklad), sazba=str(sazba), provize=str(castka))


def sestav(podminky, uol, parovani):
    vysledek = []
    for zaznam in podminky["realizace"]:
        if not all(zaznam[k] is True for k in ("certifikovan", "predano", "sla_splneno")):
            continue
        cena = cislo(zaznam["sjednana_cena_czk"])
        if cena <= 0:
            raise ValueError("Sjednaná cena realizace musí být kladná.")
        vysledek.append(polozka("realizace", "predani", zaznam["predavka"], zaznam["smlouva"],
                                zaznam["partner"], zaznam["obdobi"], cena, Decimal(100)))
    for platba in uol:
        doklad = platba["doklad"]
        if parovani.get((platba["banka"], platba["pohyb"])) != doklad:
            raise ValueError("Platba UOL nemá odpovídající pohyb na bankovním výpisu.")
        smlouva = podminky["pausaly"].get(doklad)
        if smlouva is None or smlouva["certifikovan"] is not True:
            continue
        sazba = cislo(smlouva["sazba_pct"])
        uhrazeno = cislo(platba["castka"])
        zaklad = cislo(platba["uhrazeny_pausal_bez_dph"])
        if not Decimal(10) <= sazba <= Decimal(15):
            raise ValueError("Měsíční provize je mimo sjednaný rozsah 10 až 15 procent.")
        if platba["mena"] != "CZK" or abs(zaklad) > abs(uhrazeno) or zaklad * uhrazeno <= 0:
            raise ValueError("Základ provize neodpovídá uhrazené částce v CZK.")
        vysledek.append(polozka("mrr", platba["banka"], platba["pohyb"], doklad, smlouva["partner"],
                                platba["obdobi"], zaklad, sazba))
    return vysledek
