"""Projektový model TEST pro jednofázový radiální koncový obvod TN-S."""
from decimal import Decimal, localcontext

from metodiky import hodnota, nacti, platna, text


MODEL = "radialni-TN-S-1f-odporova-zatez"


def kladne(udaj):
    vysledek = hodnota(udaj)
    if vysledek <= 0:
        raise ValueError("Vstup musí být kladný.")
    return vysledek


def kvadrat_smycky(slozky, odpor=0, reaktance=0):
    return (slozky[0] + odpor) ** 2 + (slozky[1] + reaktance) ** 2


def zobraz(cislo):
    return text(cislo.quantize(Decimal("0.0001")))


def vypocet(projekt, registr):
    m = platna(projekt, registr, MODEL)
    ochrana = m["ochrany"][projekt["ochrana"]]
    ib, napeti, km = (kladne(projekt[k]) for k in ("zatizeni_A","U0_V","delka_m"))
    km /= 1000
    jmenovity, vybavovaci, vypinaci = (kladne(ochrana[k]) for k in
        ("jmenovity_A","vybaveni_v_modelovem_case_A","vypinaci_schopnost_A"))
    koeficient = kladne(m["ulozeni"][projekt["ulozeni"]])
    dolni, horni = kladne(m["napeti_min_pomer"]), kladne(m["napeti_max_pomer"])
    mez_ubytek = kladne(m["max_ubytek_pct"])
    if not (koeficient <= 1 and dolni <= 1 <= horni and mez_ubytek <= 100
            and jmenovity <= vybavovaci <= vypinaci):
        raise ValueError("Neplatné meze metodiky nebo ochrany.")
    umin, umax = dolni * napeti, horni * napeti
    zdroj = {k: tuple(hodnota(projekt["zdroj"][k][t]) for t in ("R","X")) for k in
             ("LN_min_ohm","LN_max_ohm","LPE_min_ohm","LPE_max_ohm")}
    for druh in ("LN", "LPE"):
        minimum, maximum = zdroj[druh+"_min_ohm"], zdroj[druh+"_max_ohm"]
        if not any(minimum) or any(a > b for a,b in zip(minimum,maximum)):
            raise ValueError("Neplatná dolní či horní impedance zdroje.")
    # Nejvyšší proud u ochrany může v tomto modelu nastat na kterékoli smyčce.
    zmin2 = min(kvadrat_smycky(zdroj[k]) for k in ("LN_min_ohm","LPE_min_ohm"))
    vodice = sorted(m["vodice"], key=lambda k: kladne(k["prurez_mm2"]))
    prurezy = {kladne(k["prurez_mm2"]) for k in vodice}
    if not vodice or len(prurezy) != len(vodice):
        raise ValueError("Katalog průřezů je prázdný nebo nejednoznačný.")
    varianty = []
    for v in vodice:
        iz = kladne(v["zatizitelnost_A"]) * koeficient
        r_l, r_n, r_pe = (kladne(v[key]) * km for key in ("R_L_ohm_km","R_N_ohm_km","R_PE_ohm_km"))
        x_smycky = 2 * hodnota(v["X_ohm_km"]) * km
        ubytek = ib * (r_l + r_n)
        zs2 = kvadrat_smycky(zdroj["LPE_max_ohm"], r_l + r_pe, x_smycky)
        zln2 = kvadrat_smycky(zdroj["LN_max_ohm"], r_l + r_n, x_smycky)
        kontroly = {
            "zatizitelnost": ib <= jmenovity <= iz,
            "ubytek": 100 * ubytek <= napeti * mez_ubytek,
            "porucha_L_PE": umin**2 >= vybavovaci**2 * zs2,
            "zkrat_L_N": umin**2 >= vybavovaci**2 * zln2,
            "vypinaci_schopnost": umax**2 <= vypinaci**2 * zmin2,
        }
        varianty.append({"prurez_mm2": v["prurez_mm2"], "Iz_A": zobraz(iz), "dU_V": zobraz(ubytek),
                         "Zs_ohm": zobraz(zs2.sqrt()), "Ik_LN_min_A": zobraz(umin/zln2.sqrt()),
                         "Id_LPE_min_A": zobraz(umin/zs2.sqrt()), "chyby":[k for k,ok in kontroly.items() if not ok]})
    vyber = next((v["prurez_mm2"] for v in varianty if not v["chyby"]), None)
    return {"metodika":m["kod"],"obvod":projekt["obvod"],"den":projekt["den"],"vybrany_mm2":vyber,
            "Ik_max_u_ochrany_A":zobraz(umax/zmin2.sqrt()),"varianty":varianty}


def posud(projekt, registr):
    # Mezní rozhodnutí používají přesné druhé mocniny. Odmocnina se zaokrouhlí až pro zobrazení.
    with localcontext() as ctx:
        ctx.prec = 96
        return vypocet(projekt, registr)


def pro_spis(pozadavek):
    projekty = nacti("vedeni-projekty-test.json")
    if pozadavek in projekty:
        return posud(projekty[pozadavek], nacti("vedeni-metodiky-test.json"))
    return None
