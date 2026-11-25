from base64 import b64decode
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

from lxml import etree
from isdoc import NS, davka, sestav


class IsdocTest(unittest.TestCase):
    vzory = json.loads(Path(__file__).with_name("polozky-test.json").read_bytes())
    klic = "00000000-0000-4000-8000-000000000001"
    spis = "POL-2026-00008"
    faktura = "FAK-2026-00001"

    def test_castky_a_schema(self):
        xsd = etree.XMLSchema(etree.parse(os.environ["POLARITA_ISDOC_SCHEMA"]))
        for varianta,z,d,s in (("kladny","1072.13","225.15","1297.28"),("zaporny","368.38","77.36","445.74")):
            raw = sestav(self.faktura,self.klic,self.spis,self.vzory[varianta])
            root = etree.fromstring(raw)
            xsd.assertValid(root)
            ns = {"i":NS}
            for path,expected in (("i:TaxTotal/i:TaxAmount",d),("i:LegalMonetaryTotal/i:TaxExclusiveAmount",z),
                                  ("i:LegalMonetaryTotal/i:PayableAmount",s)):
                self.assertEqual(root.findtext(path,namespaces=ns),expected)
            root.remove(root.find("i:ID",ns))
            self.assertFalse(xsd.validate(root))

    def test_chybna_polozka(self):
        for key,val in (("sazba","12"),("mnozstvi","0"),("cena_CZK","1.001"),("cena_CZK","NaN"),("popis","")):
            p=deepcopy(self.vzory["kladny"])
            p["polozky"][0][key]=val
            with self.subTest(key=key,val=val),self.assertRaises(ValueError):
                sestav(self.faktura,self.klic,self.spis,p)

    def test_davka(self):
        a={"spis":self.spis,"faktura":self.faktura,"predavka":"ORG-UOL-2026-00001"}
        b={**a,"spis":"POL-2026-00009","faktura":"FAK-2026-00002","predavka":"ORG-UOL-2026-00002"}
        for row in (a,b):
            row["xml"] = sestav(row["faktura"],self.klic,row["spis"],self.vzory["kladny"])
        zprava=davka([b,a])
        self.assertEqual(zprava,davka([a,b]))
        for child,row in zip(ET.fromstring(zprava),[a,b],strict=True):
            self.assertEqual(b64decode(child.text,validate=True),row["xml"])
            self.assertEqual(child.get("sha256"),sha256(row["xml"]).hexdigest())
        for neplatne in ([],[a,a],[a,{**b,"xml":a["xml"]}],[{**a,"predavka":"VYD-2026-00001"}]):
            with self.assertRaises(ValueError):
                davka(neplatne)
