"""Ověření jednotlivých rizik, úplnosti soupisu a hranice modelu."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "metadata-schema-kernel"))
sys.path.insert(0, str(HERE / "revize"))
from lps import posud, pro_spis
from metodiky import nacti
from spisy_rz import id_spisu


class RizikoTest(unittest.TestCase):
    def setUp(self):
        self.p = deepcopy(nacti("lps-projekty-test.json")[str(id_spisu("kladny"))])
        self.m = deepcopy(nacti("lps-metodiky-test.json"))

    def test_prispevky(self):
        r = pro_spis(str(id_spisu("kladny")))
        self.assertEqual([x["po"] for x in r["slozky"]], ["0.00004","0.00002","0.00004","0.000004"])
        self.assertEqual((r["pred"],r["po"],r["po_v_mezi"]),("0.0004","0.000104",True))
        r = pro_spis(str(id_spisu("zaporny")))
        self.assertEqual((r["pred"],r["po"],r["po_v_mezi"]),("0.001","0.00026",False))
        self.assertIsNone(pro_spis("neznamy"))

    def test_presna_mez(self):
        self.p["expozice"]["okoli_pripojky"]["podil_ztraty"] = "0"
        self.m[0]["mez_rocni_ztraty"] = "0.0001"
        self.assertTrue(posud(self.p,self.m)["po_v_mezi"])
        self.p["hustota_na_km2_rok"] = "2.0001"
        self.assertFalse(posud(self.p,self.m)["po_v_mezi"])

    def test_chybi_vstup(self):
        for project in ({**self.p,"expozice":{}},{**self.p,"opatreni":"jine"},{**self.p,"hustota_na_km2_rok":"0"},
                        {**self.p,"ucel":"provoz"},{**self.p,"den":"2030-01-01"}):
            with self.subTest(project=project),self.assertRaises(ValueError):
                posud(project,self.m)
        self.p["expozice"]["objekt"]["podil_ztraty"] = "1.1"
        with self.assertRaises(ValueError):
            posud(self.p,self.m)
        self.p["expozice"]["objekt"]["podil_ztraty"] = "0.5"
        self.m[0]["slozky"]["objekt"]["P_po"] = "1"
        with self.assertRaises(ValueError):
            posud(self.p,self.m)
