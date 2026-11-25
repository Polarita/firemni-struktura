"""Nabídka XC4 NZ a její devět kontrolovaných skupin. Částky za položku se zaokrouhlují na haléře."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import re

from lxml import etree as ET

VRSTVY = ("Silnoproud a hromosvody", "Slaboproud a DLM", "Zemní práce a vytýčení sítí",
          "Bourání, drážky a prostupy", "Protipožární ucpávky EI", "Zednické zapravení omítek",
          "Příprava podkladu a malby", "Inženýrská a revizní činnost", "Vedlejší rozpočtové náklady")
MARK = "Vrstva přípomocí Polarity "
LIMIT = 16 * 1024 * 1024


def cislo(value, digits):
    raw = str(value)
    if not re.fullmatch(r"-?[0-9]{1,19}(?:\.[0-9]{1," + str(digits) + r"})?", raw):
        raise ValueError("Množství nebo jednotková cena má nepodporovaný rozsah či přesnost.")
    return Decimal(raw)


def castka(line):
    with localcontext() as ctx:
        ctx.prec = 64
        return (line["mnozstvi"] * line["cena"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parser():
    return ET.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)


def over_xml(raw, schema):
    if len(raw) > LIMIT:
        raise ValueError("Soubor XC4 přesahuje povolenou velikost.")
    root = ET.fromstring(raw, parser())
    if root.getroottree().docinfo.doctype:
        raise ValueError("Rozpočet obsahuje deklaraci DTD.")
    ET.XMLSchema(ET.parse(str(schema), parser())).assertValid(root)
    if root.findtext("obsah") not in (None, "PZ"):
        raise ValueError("Očekávána nabídka zhotovitele XC4 NZ.")
    return root


def polozky(root):
    units = {u.findtext("id_mj"): u.findtext("znacka") for u in root.findall("merneJednotky/MJ")}
    rows = {}
    for el in root.findall(".//stavDil/polozky/polozka"):
        key = el.findtext("id_polozka")
        if key in rows:
            raise ValueError("Identifikátor položky se opakuje.")
        notes = (el.findtext("popis") or "").splitlines()
        tags = [n[len(MARK):] for n in notes if n.startswith(MARK)]
        if tags and (len(tags) != 1 or tags[0] not in tuple(map(str, range(1,10)))):
            raise ValueError("Položka obsahuje nejednoznačné označení skupiny.")
        rows[key] = {"kod": el.findtext("znacka"), "nazev": el.findtext("nazev"),
                     "mj": units[el.findtext("id_mj")], "mnozstvi": cislo(el.findtext("mnozstvi"), 6),
                     "cena": cislo(el.findtext("joc"), 4), "vrstva": int(tags[0]) if tags else None,
                     "objekt": el.xpath("ancestor::objekt[1]/znacka/text()")[0],
                     "dil": el.xpath("ancestor::stavDil[1]/znacka/text()")[0], "xml": el}
    if not rows:
        raise ValueError("Rozpočet neobsahuje položky.")
    return rows


def souhrn(rows):
    covered = {r["vrstva"] for r in rows.values()}
    if None in covered or covered != set(range(1, 10)):
        raise ValueError("FAIL_CLOSED · Každá položka potřebuje skupinu a nabídka musí doložit všech devět skupin.")
    with localcontext() as ctx:
        ctx.prec = 64
        return sum((castka(r) for r in rows.values()), Decimal("0.00"))


def pole(parent, **fields):
    for name, value in fields.items():
        ET.SubElement(parent, name).text = str(value)


def sestav(data):
    root = ET.Element("XC4")
    pole(root, verze="4.4", zdroj="Polarita TEST", nazev=data["nazev"], obsah="PZ", mena="CZK",
         sazba_dph1=0, sazba_dph2=0, sazba_dph3=0, jazyk="cs", desMistMnozstviPolRoz=6)
    kl = ET.SubElement(root, "KL")
    pole(kl, znacka="TEST", nazev="Položky testovací nabídky")
    head = ET.SubElement(ET.SubElement(kl, "struktura_KL"), "polozka_KL")
    pole(head, id_PKL="PRACE", znacka="PRACE", typ_vypoctu="POLOZKY_ROZPOCTU")
    project = ET.SubElement(root, "stavba")
    pole(project, znacka=data["kod"], nazev=data["nazev"], varianta="TEST")
    obj = ET.SubElement(ET.SubElement(project, "objekty"), "objekt")
    pole(obj, id_objekt="SO1", znacka="SO1", nazev=data["objekt"])
    parts = ET.SubElement(obj, "stavDily")
    units = {u:f"MJ{i}" for i,u in enumerate(sorted({r["mj"] for r in data["polozky"]}),1)}
    groups = {}
    for i, row in enumerate(data["polozky"], 1):
        n = row["vrstva"]
        if type(n) is not int or not 1 <= n <= len(VRSTVY):
            raise ValueError("Neznámá vrstva rozpočtu.")
        if n not in groups:
            part = ET.SubElement(parts, "stavDil")
            pole(part, id_stavdil=f"D{n}", znacka=f"D{n}", nazev=VRSTVY[n-1], id_PKL="PRACE")
            groups[n] = ET.SubElement(part, "polozky")
        el = ET.SubElement(groups[n], "polozka")
        pole(el, id_polozka=row["id"], znacka=row["kod"], nazev=row["nazev"], varianta="A",
             por_cislo=i, popis=MARK+str(n), id_PKL="PRACE", cenova_soustava="TEST",
             id_mj=units[row["mj"]], mnozstvi=cislo(row["mnozstvi"],6), joc=cislo(row["cena"],4),
             typ_sazby_dph="SAZBA3")
    measures = ET.SubElement(root,"merneJednotky")
    for unit,key in units.items():
        pole(ET.SubElement(measures,"MJ"), id_mj=key, znacka=unit)
    return root


def xml_bytes(root):
    return ET.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
