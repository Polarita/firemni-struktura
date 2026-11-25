"""Tiskový stejnopis z ověřené tuzemské faktury ISDOC."""
from datetime import date
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET

from isdoc import NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdf_qr import precti, vytiskni

TEST_IBAN = "CZ7900000000000000000000"  # Nulový účet a kód banky 0000 pouze pro TEST.
NSMAP = {"": NS}


def povinne(node, cesta):
    text = node.findtext(cesta, namespaces=NSMAP)
    if not text:
        raise ValueError("V podkladu tisku chybí " + cesta)
    return text


def model(xml, spis):
    root = ET.fromstring(xml)
    cislo = povinne(root, "ID")
    shoda = re.fullmatch(r"FAK-([0-9]{4})-([0-9]{5})", cislo)
    if (not shoda or povinne(root, "LocalCurrencyCode") != "CZK" or
            povinne(root, "Note") != f"TEST – vzor bez požadavku na úhradu. Spis {spis}."):
        raise ValueError("Podklad neodpovídá korunové faktuře daného spisu.")
    vs = "".join(shoda.groups())
    castka = povinne(root, "LegalMonetaryTotal/PayableAmount")
    if not re.fullmatch(r"[0-9]{1,7}\.[0-9]{2}", castka):
        raise ValueError("Částku nelze zapsat do testovací QR platby.")
    spayd = f"SPD*1.0*ACC:{TEST_IBAN}*AM:{castka}*CC:CZK*X-VS:{vs}*MSG:TEST NEHRADIT"
    radky = []
    for line in root.findall("InvoiceLines/InvoiceLine", NSMAP):
        qty = line.find("InvoicedQuantity", NSMAP)
        radky.append({"popis": povinne(line, "Item/Description"), "pocet": povinne(line, "InvoicedQuantity"),
                      "jednotka": {"HUR":"h", "C62":"ks"}[qty.attrib["unitCode"]],
                      "cena": povinne(line, "UnitPrice"), "zaklad": povinne(line, "LineExtensionAmount"),
                      "sazba": povinne(line, "ClassifiedTaxCategory/Percent")})
    return {"cislo": cislo, "spis": spis, "datum": date.fromisoformat(povinne(root, "IssueDate")).strftime("%d. %m. %Y"),
            "dodavatel": povinne(root, "AccountingSupplierParty/Party/PartyName/Name"),
            "odberatel": povinne(root, "AccountingCustomerParty/Party/PartyName/Name"),
            "zaklad": povinne(root, "LegalMonetaryTotal/TaxExclusiveAmount"),
            "dan": povinne(root, "TaxTotal/TaxAmount"), "celkem": castka, "vs": vs, "radky": radky}, spayd


def stejnopis(xml, spis):
    data, payload = model(xml, spis)
    pdf = vytiskni(Path(__file__).with_name("faktura.typ"), data, payload)
    if precti(pdf) != payload:
        raise ValueError("QR přečtený z výtisku nesouhlasí s podkladem ISDOC.")
    return pdf
