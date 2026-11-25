"""Regrese fázové bilance a omezení modelových nabíječek."""
from copy import deepcopy
from decimal import Decimal
from itertools import product
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "metadata-schema-kernel"))
sys.path.insert(0, str(HERE / "revize"))
from dlm import FAZE, bilance, pro_spis
from metodiky import SOUBORY
from spisy_rz import id_spisu


class BilanceTest(unittest.TestCase):
    def setUp(self):
        self.metody = json.loads((SOUBORY / "dlm-metodiky-test.json").read_bytes())
        self.projekt = json.loads((SOUBORY / "dlm-projekty-test.json").read_bytes())[str(id_spisu("kladny"))]

    def test_dokumentovane_spisy(self):
        kladny = pro_spis(str(id_spisu("kladny")))
        self.assertEqual(kladny["soudoby_prikon_W"], "9200")
        self.assertEqual(kladny["vozidla_A"], {"EV-A": 9, "EV-B": 9})
        self.assertEqual([r["rezerva_po_EV_W"] for r in kladny["faze"].values()], ["0", "690", "3910"])
        zaporny = pro_spis(str(id_spisu("zaporny")))
        self.assertEqual(zaporny["pretizene_faze"], ["L2"])
        self.assertEqual(zaporny["faze"]["L2"]["rezerva_po_EV_W"], "-0.01")
        self.assertEqual(zaporny["vozidla_A"], {"EV-A": 0, "EV-B": 0})
        self.assertIsNone(pro_spis("cizi-spis"))

    def test_rozsah_zatizeni(self):
        # Nezávislá kontrola účtování v ampérech pro všechny kombinace zatížení.
        for limity in product((4, 14, 20, 32, 128), repeat=3):
            self.projekt["limit_A"] = dict(zip(FAZE, map(str, limity)))
            vysledek = bilance(self.projekt, self.metody)
            tri, jedna = vysledek["vozidla_A"].values()
            ev = (tri + jedna, tri, tri)
            zaklad = (14, 20, 6)
            with self.subTest(limity=limity):
                for a in (tri, jedna):
                    self.assertTrue(a == 0 or 6 <= a <= 16)
                for i, f in enumerate(FAZE):
                    faze = vysledek["faze"][f]
                    self.assertEqual(faze["prideleno_EV_A"], ev[i])
                    rezerva = limity[i] - zaklad[i] - ev[i]
                    self.assertEqual(Decimal(faze["rezerva_po_EV_W"]), rezerva * 230)
                    if vysledek["pretizene_faze"]:
                        self.assertEqual(ev, (0, 0, 0))
                    else:
                        self.assertGreaterEqual(rezerva, 0)
                if limity == (128, 128, 128):
                    self.assertEqual((tri, jedna), (16, 16))

    def test_minimum_na_hrane_a_jednofazovy_zbytek(self):
        self.projekt["limit_A"]["L2"] = "25.9999"
        self.assertEqual(bilance(self.projekt,self.metody)["vozidla_A"], {"EV-A": 0, "EV-B": 16})
        self.projekt["limit_A"]["L2"] = "26"
        self.assertEqual(bilance(self.projekt,self.metody)["vozidla_A"], {"EV-A": 6, "EV-B": 12})

    def test_chybny_projekt(self):
        for k, v in (("den","2027-01-01"),("model","realny"),("ucel","provoz"),
                     ("fazove_napeti_V","0"),("fazove_napeti_V","NaN"),("skupiny",[]),
                     ("limit_A",{"L1":"32"}),("vozidla",{}),("vozidla",self.projekt["vozidla"] * 2)):
            with self.subTest(k=k,v=v), self.assertRaises(ValueError):
                bilance({**self.projekt,k:v},self.metody)
        for k,v in (("faze",["L1","L1"]),("faze",["L4"]),("pozadavek_A",True),("pozadavek_A",4)):
            vozidlo = {**self.projekt["vozidla"][0], k:v}
            with self.subTest(k=k,v=v), self.assertRaises(ValueError):
                bilance({**self.projekt,"vozidla":[vozidlo]},self.metody)

    def test_chybna_metodika(self):
        with self.assertRaises(ValueError):
            bilance(self.projekt,self.metody * 2)
        m = deepcopy(self.metody)
        m[0]["soudobost"]["stala"] = "1.01"
        with self.assertRaises(ValueError):
            bilance(self.projekt,m)
