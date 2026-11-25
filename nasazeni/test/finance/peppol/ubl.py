"""Převod vydané tuzemské faktury TEST do Peppol BIS Billing, profil 01."""
import re
from xml.etree import ElementTree as ET

INV = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
ISDOC = {"":"http://isdoc.cz/namespace/2013"}
PROFIL = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
CUSTOM = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"

for prefix, ns in (("",INV),("cac",CAC),("cbc",CBC)):
    ET.register_namespace(prefix, ns)


def hodnota(node, path):
    value = node.findtext(path, namespaces=ISDOC)
    if not value:
        raise ValueError("Chybí údaj v ISDOC pro Peppol: " + path)
    return value


def cast(node, tag):
    return ET.SubElement(node, f"{{{CAC}}}{tag}")


def udaj(node, tag, value, **attrs):
    ET.SubElement(node, f"{{{CBC}}}{tag}", attrs).text = value


def adresa_uctu_test(ident):
    zaklad = f"952{ident:09d}"
    kontrola = -sum(int(n)*(1 if i%2==0 else 3) for i,n in enumerate(zaklad)) % 10
    return zaklad + str(kontrola)


def strana(doc, root, typ, ident):
    xml = root.find(typ+"/Party", ISDOC)
    party = cast(cast(doc,typ),"Party")
    udaj(party,"EndpointID",adresa_uctu_test(ident),schemeID="0088")
    adresa = cast(party,"PostalAddress")
    udaj(adresa,"StreetName",hodnota(xml,"PostalAddress/StreetName")+" "+hodnota(xml,"PostalAddress/BuildingNumber"))
    udaj(adresa,"CityName",hodnota(xml,"PostalAddress/CityName"))
    udaj(adresa,"PostalZone",hodnota(xml,"PostalAddress/PostalZone"))
    udaj(cast(adresa,"Country"),"IdentificationCode",hodnota(xml,"PostalAddress/Country/IdentificationCode"))
    if typ == "AccountingSupplierParty":
        tax = cast(party,"PartyTaxScheme")
        udaj(tax,"CompanyID","CZ00000000")
        udaj(cast(tax,"TaxScheme"),"ID","VAT")
    udaj(cast(party,"PartyLegalEntity"),"RegistrationName",hodnota(xml,"PartyName/Name"))


def kategorie(parent, tag, percent):
    sazba = cast(parent,tag)
    udaj(sazba,"ID","S")
    udaj(sazba,"Percent",percent)
    udaj(cast(sazba,"TaxScheme"),"ID","VAT")


def faktura_ubl(raw, case):
    root = ET.fromstring(raw)
    cislo = hodnota(root,"ID")
    if (not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}",case)
            or not re.fullmatch(r"FAK-[0-9]{4}-[0-9]{5}",cislo)
            or hodnota(root,"Note") != f"TEST – vzor bez požadavku na úhradu. Spis {case}."
            or hodnota(root,"LocalCurrencyCode") != "CZK" or hodnota(root,"DocumentType") != "1"):
        raise ValueError("Tento převod potřebuje tuzemskou fakturu TEST příslušného spisu.")
    doc = ET.Element(f"{{{INV}}}Invoice")
    for tag, value in (("CustomizationID",CUSTOM),("ProfileID",PROFIL),("ID",cislo),
                       ("IssueDate",hodnota(root,"IssueDate")),("InvoiceTypeCode","380"),
                       ("Note",hodnota(root,"Note")),("DocumentCurrencyCode","CZK"),("BuyerReference",case)):
        udaj(doc,tag,value)
    strana(doc,root,"AccountingSupplierParty",0)
    strana(doc,root,"AccountingCustomerParty",int(case.replace("-","")[3:]))
    udaj(cast(doc,"PaymentTerms"),"Note","Zkušební faktura bez požadavku na úhradu.")
    tax = cast(doc,"TaxTotal")
    def cena(node, tag, value):
        udaj(node,tag,value,currencyID="CZK")
    cena(tax,"TaxAmount",hodnota(root,"TaxTotal/TaxAmount"))
    for src in root.findall("TaxTotal/TaxSubTotal",ISDOC):
        sub = cast(tax,"TaxSubtotal")
        for tag in ("TaxableAmount","TaxAmount"):
            cena(sub,tag,hodnota(src,tag))
        kategorie(sub,"TaxCategory",hodnota(src,"TaxCategory/Percent"))
    money = cast(doc,"LegalMonetaryTotal")
    for tag, path in (("LineExtensionAmount","TaxExclusiveAmount"),("TaxExclusiveAmount","TaxExclusiveAmount"),
                      ("TaxInclusiveAmount","TaxInclusiveAmount"),("PayableAmount","PayableAmount")):
        cena(money,tag,hodnota(root,"LegalMonetaryTotal/"+path))
    for src in root.findall("InvoiceLines/InvoiceLine",ISDOC):
        line = cast(doc,"InvoiceLine")
        udaj(line,"ID",hodnota(src,"ID"))
        qty = src.find("InvoicedQuantity",ISDOC)
        udaj(line,"InvoicedQuantity",hodnota(src,"InvoicedQuantity"),unitCode=qty.attrib["unitCode"])
        cena(line,"LineExtensionAmount",hodnota(src,"LineExtensionAmount"))
        item = cast(line,"Item")
        udaj(item,"Name",hodnota(src,"Item/Description"))
        kategorie(item,"ClassifiedTaxCategory",hodnota(src,"ClassifiedTaxCategory/Percent"))
        cena(cast(line,"Price"),"PriceAmount",hodnota(src,"UnitPrice"))
    return ET.tostring(doc, encoding="utf-8", xml_declaration=True)
