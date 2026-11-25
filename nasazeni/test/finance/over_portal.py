"""Zkouška stažení dvou nezaměnitelných faktur i číslovaných předávek přes ředitelství."""
from base64 import b64decode
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET

from isdoc import NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"sanony"))
from overeni import pripojeni, prihlasit


def over(origin, heslo, protokol):
    radky = re.findall(r"^(POL-[0-9]{4}-[0-9]{5}) (FAK-[0-9]{4}-[0-9]{5}) (ORG-UOL-[0-9]{4}-[0-9]{5}) ([a-f0-9]{64})$",protokol,re.M)
    if len(radky)!=2 or radky[0][0]==radky[1][0]:
        raise ValueError("Chybí dva nezávislé vydané exporty.")
    call = pripojeni(origin)
    prihlasit(call,heslo)
    base = "/lhutnik-test/api/"
    for i,(spis,faktura,predavka,digest) in enumerate(radky):
        karta = json.loads(call("GET",base+"spisy/"+spis))
        otisky = {d["cislo"]:d["export_sha256"] for d in karta["doklady_registru"]}
        cesta = base+"finance/"+spis+"/"
        raw = call("GET", cesta+faktura+".isdoc")
        batch = call("GET", cesta+predavka+".xml")
        pdf = call("GET", cesta+faktura+".pdf")
        fakturacni_radek = next(d for d in karta["doklady_registru"] if d["cislo"] == faktura)
        if not pdf.startswith(b"%PDF-") or sha256(pdf).hexdigest() != fakturacni_radek["pdf_sha256"]:
            raise ValueError("Stažený tisk nesouhlasí s vydanou fakturou.")
        invoice = ET.fromstring(raw)
        if (sha256(raw).hexdigest()!=digest or otisky[faktura]!=digest or sha256(batch).hexdigest()!=otisky[predavka]
                or invoice.findtext(f"{{{NS}}}ID")!=faktura):
            raise ValueError("Nesouhlasí vazba exportu nebo kontrolní součet.")
        [priloha] = ET.fromstring(batch).findall("Doklad")
        if (priloha.get("predavka")!=predavka or priloha.get("spis")!=spis or priloha.get("sha256")!=digest
                or b64decode(priloha.text,validate=True)!=raw):
            raise ValueError("Účetní předávka neobsahuje původní fakturu.")
        jiny = base+"finance/"+radky[1-i][0]+"/"
        for soubor in (faktura+".isdoc",faktura+".pdf",predavka+".xml"):
            call("GET",jiny+soubor,status=404)
        print(spis,faktura,invoice.findtext(f"{{{NS}}}LegalMonetaryTotal/{{{NS}}}PayableAmount"),"CZK",digest)


if __name__ == "__main__":
    over(sys.argv[1],sys.stdin.readline().rstrip("\r\n"),Path(sys.argv[2]).read_text())
