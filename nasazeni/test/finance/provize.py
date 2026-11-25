"""Položky provizního ledgeru z potvrzených realizací a plateb spárovaných UOL."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "balicky/S3-konfigurator-a-tarify"))
import pricing

HALER = Decimal("0.01")


def cislo(hodnota):
    if not isinstance(hodnota, str):
        raise ValueError("Účetní hodnota musí být desetinné číslo zapsané jako text.")
    vysledek = Decimal(hodnota)
    if not vysledek.is_finite() or vysledek != vysledek.quantize(HALER):
        raise ValueError("Chybná přesnost účetní hodnoty.")
    return vysledek


def polozka(druh, zdroj, udalost, doklad, partner, obdobi, zaklad, sazba, castka):
    if not all(isinstance(x, str) and x.strip() for x in (zdroj, udalost, doklad, partner)):
        raise ValueError("Chybí identita zdroje, dokladu nebo partnera.")
    mesic = date.fromisoformat(obdobi)
    if mesic.day != 1:
        raise ValueError("Účetní období musí začínat prvního dne měsíce.")
    return dict(druh=druh, zdroj=zdroj, udalost=udalost, doklad=doklad, partner=partner,
                obdobi=mesic.isoformat(), zaklad=str(zaklad), sazba=str(sazba), provize=str(castka))


def sestav(podminky, uol, parovani):
    cenik = pricing.load_price_list()
    vysledek = []
    for zaznam in podminky["realizace"]:
        if not all(zaznam[k] is True for k in ("certifikovan", "predano", "sla_splneno")):
            continue
        cena = cislo(zaznam["sjednana_cena_czk"])
        if cena <= 0:
            raise ValueError("Sjednaná cena realizace musí být kladná.")
        vysledek.append(polozka("realizace", "predani", zaznam["predavka"], zaznam["smlouva"],
                                zaznam["partner"], zaznam["obdobi"], cena, Decimal(100), cena))
    for platba in uol:
        doklad = platba["doklad"]
        if parovani.get((platba["banka"], platba["pohyb"])) != doklad:
            raise ValueError("Platba UOL nemá odpovídající pohyb na bankovním výpisu.")
        smlouva = podminky["pausaly"].get(doklad)
        if smlouva is None or smlouva["certifikovan"] is not True:
            continue
        pocet = smlouva["aktivni_objekty"]
        sazba = pricing.partner_commission_pct(cenik, pocet)
        if sazba == 0:
            continue
        uhrazeno = cislo(platba["castka"])
        zaklad = cislo(platba["uhrazeny_pausal_bez_dph"])
        if platba["mena"] != "CZK" or abs(zaklad) > abs(uhrazeno) or zaklad * uhrazeno <= 0:
            raise ValueError("Základ provize neodpovídá uhrazené částce v CZK.")
        castka = pricing.partner_commission(cenik, abs(zaklad), pocet).copy_sign(zaklad)
        vysledek.append(polozka("mrr", platba["banka"], platba["pohyb"], doklad, smlouva["partner"],
                                platba["obdobi"], zaklad, sazba, castka))
    return vysledek
