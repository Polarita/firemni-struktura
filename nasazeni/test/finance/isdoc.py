"""Vytvoří tuzemskou korunovou fakturu TEST, součty zaokrouhluje po řádcích."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import re
from uuid import UUID
from xml.etree import ElementTree as ET


NS = "http://isdoc.cz/namespace/2013"
HALER = Decimal("0.01")
VERZE = "6.0.2"


def castka(value):
    return value.quantize(HALER, rounding=ROUND_HALF_UP)


def cislo(udaj, mista):
    if not isinstance(udaj, str) or not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,"+str(mista)+r"})?", udaj):
        raise ValueError("Chybné číslo ve fakturačním podkladu.")
    return Decimal(udaj)


def pole(parent, hodnoty):
    for jmeno, hodnota in hodnoty.items():
        ET.SubElement(parent, jmeno).text = str(hodnota)


def strana(faktura, druh, ident, jmeno):
    party = ET.SubElement(ET.SubElement(faktura, druh), "Party")
    pole(ET.SubElement(party, "PartyIdentification"), {"ID":ident})
    pole(ET.SubElement(party, "PartyName"), {"Name":jmeno})
    adresa = ET.SubElement(party, "PostalAddress")
    pole(adresa, {"StreetName":"Modelová", "BuildingNumber":"1", "CityName":"Obec TEST", "PostalZone":"00000"})
    pole(ET.SubElement(adresa, "Country"), {"IdentificationCode":"CZ", "Name":"Česko"})


def sestav(cislo_faktury, pozadavek, spis, podklad):
    if not re.fullmatch(r"FAK-[0-9]{4}-[0-9]{5}", cislo_faktury) or not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", spis):
        raise ValueError("Neplatné číslo faktury nebo spisu.")
    if not podklad["polozky"] or not podklad["odberatel"].strip():
        raise ValueError("Chybí odběratel nebo položky.")
    den = date.fromisoformat(podklad["datum"]).isoformat()
    faktura = ET.Element("Invoice", xmlns=NS, version=VERZE)
    pole(faktura, {"DocumentType":"1","ID":cislo_faktury,"UUID":str(UUID(pozadavek)),
                   "IssuingSystem":"Ředitelství Polarity TEST","IssueDate":den,"TaxPointDate":den,
                   "VATApplicable":"true","ElectronicPossibilityAgreementReference":"Modelová fakturace TEST",
                   "Note":f"TEST – vzor bez požadavku na úhradu. Spis {spis}.","LocalCurrencyCode":"CZK",
                   "CurrRate":1,"RefCurrRate":1})
    strana(faktura,"AccountingSupplierParty","TEST-DODAVATEL","Polarita TEST")
    strana(faktura,"AccountingCustomerParty","TEST-"+spis,podklad["odberatel"])
    radky = ET.SubElement(faktura,"InvoiceLines")
    sazby = {}
    for i, r in enumerate(podklad["polozky"], 1):
        mnozstvi, cena = cislo(r["mnozstvi"],3), cislo(r["cena_CZK"],2)
        if (not mnozstvi or not cena or r["sazba"] != "21" or r["jednotka"] not in ("HUR","C62")
                or not r["popis"].strip()):
            raise ValueError("Položka není podporovaným druhem modelové korunové faktury.")
        sazba = int(r["sazba"])
        bez = castka(mnozstvi*cena)
        dan = castka(bez*sazba/100)
        radek = ET.SubElement(radky,"InvoiceLine")
        pole(radek,{"ID":i})
        ET.SubElement(radek,"InvoicedQuantity",unitCode=r["jednotka"]).text = str(mnozstvi)
        pole(radek,{"LineExtensionAmount":bez,"LineExtensionAmountTaxInclusive":bez+dan,
                    "LineExtensionTaxAmount":dan,"UnitPrice":castka(cena),
                    "UnitPriceTaxInclusive":castka(cena*(100+sazba)/100)})
        pole(ET.SubElement(radek,"ClassifiedTaxCategory"),{"Percent":sazba,"VATCalculationMethod":0,"VATApplicable":"true"})
        pole(ET.SubElement(radek,"Item"),{"Description":r["popis"]})
        zaklad, dph = sazby.get(sazba,(0,0))
        sazby[sazba] = zaklad+bez, dph+dan
    celkem = ET.SubElement(faktura,"TaxTotal")
    for sazba,(zaklad,dph) in sorted(sazby.items()):
        skupina = ET.SubElement(celkem,"TaxSubTotal")
        pole(skupina,{"TaxableAmount":zaklad,"TaxAmount":dph,"TaxInclusiveAmount":zaklad+dph,
                      "AlreadyClaimedTaxableAmount":"0.00","AlreadyClaimedTaxAmount":"0.00",
                      "AlreadyClaimedTaxInclusiveAmount":"0.00","DifferenceTaxableAmount":zaklad,
                      "DifferenceTaxAmount":dph,"DifferenceTaxInclusiveAmount":zaklad+dph})
        pole(ET.SubElement(skupina,"TaxCategory"),{"Percent":sazba})
    bez = sum(z for z,_ in sazby.values())
    dan = sum(d for _,d in sazby.values())
    pole(celkem,{"TaxAmount":dan})
    pole(ET.SubElement(faktura,"LegalMonetaryTotal"),{"TaxExclusiveAmount":bez,"TaxInclusiveAmount":bez+dan,
         "AlreadyClaimedTaxExclusiveAmount":"0.00","AlreadyClaimedTaxInclusiveAmount":"0.00",
         "DifferenceTaxExclusiveAmount":bez,"DifferenceTaxInclusiveAmount":bez+dan,
         "PaidDepositsAmount":"0.00","PayableAmount":bez+dan})
    return ET.tostring(faktura,encoding="utf-8",xml_declaration=True)


def davka(doklady):
    """XML předávka mezi vlastními službami TEST. Obsah příloh zachová po bajtech."""
    from base64 import b64encode
    if not doklady or len({d["faktura"] for d in doklady}) != len(doklady) or len({d["predavka"] for d in doklady}) != len(doklady):
        raise ValueError("Prázdná dávka nebo duplicitní doklad.")
    root = ET.Element("Predavka",format="Polarita-UOL-TEST-1",pocet=str(len(doklady)))
    for d in sorted(doklady,key=lambda row:row["predavka"]):
        if not re.fullmatch(r"ORG-UOL-[0-9]{4}-[0-9]{5}",d["predavka"]):
            raise ValueError("Chybná řada účetní předávky.")
        xml = ET.fromstring(d["xml"])
        if (xml.tag != f"{{{NS}}}Invoice" or xml.findtext(f"{{{NS}}}ID") != d["faktura"]
                or xml.findtext(f"{{{NS}}}Note") != f"TEST – vzor bez požadavku na úhradu. Spis {d['spis']}."):
            raise ValueError("Nesouhlasí spis nebo číslo přikládané faktury.")
        zaznam = ET.SubElement(root,"Doklad",spis=d["spis"],predavka=d["predavka"],faktura=d["faktura"],
                               sha256=sha256(d["xml"]).hexdigest(),kodovani="base64")
        zaznam.text = b64encode(d["xml"]).decode("ascii")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)
