"""Roční podíl majetkové ztráty v modelu TEST pro čtyři zdroje škod."""
from decimal import Decimal, localcontext

from metodiky import hodnota, nacti, platna, text


ZDROJE = ("objekt", "okoli_objektu", "pripojka", "okoli_pripojky")


def podil(udaj):
    vysledek = hodnota(udaj)
    if vysledek > 1:
        raise ValueError("Podíl ztráty nebo pravděpodobnost musí být v intervalu 0 až 1.")
    return vysledek


def posud(projekt, metodiky):
    metoda = platna(projekt, metodiky, "objekt-test-majetkova-ztrata")
    mez = podil(metoda["mez_rocni_ztraty"])
    hustota = hodnota(projekt["hustota_na_km2_rok"])
    expozice = projekt["expozice"]
    opatreni = projekt["opatreni"]
    if (not mez or not hustota or opatreni != metoda["opatreni"]
            or set(expozice) != set(ZDROJE) or set(metoda["slozky"]) != set(ZDROJE)):
        raise ValueError("Chybí mez, hustota, popis opatření nebo úplný soupis zdrojů.")
    pred = po = Decimal(0)
    slozky = []
    with localcontext() as ctx:
        ctx.prec = 64
        for k in ZDROJE:
            m, e = metoda["slozky"][k], expozice[k]
            plocha = hodnota(e["plocha_m2"])
            cetnost = hustota * plocha / 1_000_000
            ztrata = podil(e["podil_ztraty"])
            p_pred, p_po = podil(m["P_pred"]), podil(m["P_po"])
            if p_po > p_pred:
                raise ValueError("Ochranné opatření v této metodice zvyšuje pravděpodobnost škody.")
            r_pred, r_po = cetnost * p_pred * ztrata, cetnost * p_po * ztrata
            pred += r_pred
            po += r_po
            slozky.append({"nazev":m["popis"],"cetnost_rok":text(cetnost),"pred":text(r_pred),"po":text(r_po)})
        return {"metodika":metoda["kod"],"den":projekt["den"],"opatreni":metoda["popis_opatreni"],"mez":text(mez),
                "pred":text(pred),"po":text(po),"pred_v_mezi":pred <= mez,"po_v_mezi":po <= mez,"slozky":slozky}


def pro_spis(pozadavek):
    projekty = nacti("lps-projekty-test.json")
    if pozadavek in projekty:
        return posud(projekty[pozadavek], nacti("lps-metodiky-test.json"))
    return None
