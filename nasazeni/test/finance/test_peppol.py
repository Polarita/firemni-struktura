"""Kladné a záporné kontroly nad skutečným XSD a oběma sadami Schematron."""
import json
import os
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

from lxml import etree

from isdoc import sestav
from peppol.kontrola import over
from peppol.ubl import CAC, CBC, faktura_ubl


class PeppolTest(unittest.TestCase):
    spis = "POL-2026-00008"
    faktura = "FAK-2026-00001"

    def setUp(self):
        self.pravidla = Path(os.environ["POLARITA_PEPPOL_PRAVIDLA"])
        vzory = json.loads(Path(__file__).with_name("polozky-test.json").read_bytes())
        xml = sestav(self.faktura,"00000000-0000-4000-8000-000000000001",self.spis,vzory["kladny"])
        self.ubl = faktura_ubl(xml, self.spis)

    def test_vydani(self):
        over(self.ubl,self.pravidla)
        root = ET.fromstring(self.ubl)
        self.assertEqual(root.findtext(f"{{{CBC}}}ID"),self.faktura)
        self.assertEqual(root.findtext(f"{{{CAC}}}LegalMonetaryTotal/{{{CBC}}}PayableAmount"),"1297.28")
        ids = [e.text for e in root.iter(f"{{{CBC}}}EndpointID")]
        self.assertEqual(len(set(ids)),2)
        self.assertTrue(all(len(v)==13 and v.isdigit() for v in ids))

    def test_chyby_obou_sad(self):
        root = ET.fromstring(self.ubl)
        root.remove(root.find(f"{{{CBC}}}BuyerReference"))
        root.find(f"{{{CAC}}}LegalMonetaryTotal/{{{CBC}}}PayableAmount").text = "5.00"
        with self.assertRaises(ValueError) as err:
            over(ET.tostring(root),self.pravidla)
        self.assertIn("PEPPOL-EN16931-R003",str(err.exception))
        self.assertIn("BR-CO-16",str(err.exception))

    def test_chyba_struktury(self):
        with self.assertRaises(etree.DocumentInvalid):
            over(self.ubl.replace(b"cbc:IssueDate",b"cbc:NeznamePole"),self.pravidla)
