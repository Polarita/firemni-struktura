"""Referenční a mezní zkoušky modelu jednoho koncového obvodu."""
from copy import deepcopy
import json
from math import hypot
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "metadata-schema-kernel"))
sys.path.insert(0, str(HERE / "revize"))
from metodiky import SOUBORY
from spisy_rz import id_spisu
from vedeni import posud, pro_spis


class VedeniTest(unittest.TestCase):
    def setUp(self):
        self.p = json.loads((SOUBORY/"vedeni-projekty-test.json").read_bytes())[str(id_spisu("kladny"))]
        self.registr = json.loads((SOUBORY/"vedeni-metodiky-test.json").read_bytes())

    def test_spisy(self):
        res = pro_spis(str(id_spisu("kladny")))
        self.assertEqual(res["vybrany_mm2"], "2.5")
        self.assertEqual(res["varianty"][0]["chyby"], ["zatizitelnost","ubytek"])
        kandidat = res["varianty"][1]
        self.assertEqual(kandidat["dU_V"], "6")
        # Nezávislé dosazení R, X a počátečních impedancí z obou různých smyček.
        self.assertAlmostEqual(float(kandidat["Zs_ohm"]), hypot(0.74, 0.064), places=4)
        self.assertAlmostEqual(float(kandidat["Id_LPE_min_A"]), 218.5 / hypot(0.74, 0.064), places=4)
        self.assertAlmostEqual(float(kandidat["Ik_LN_min_A"]), 218.5 / hypot(0.62, 0.054), places=4)
        self.assertAlmostEqual(float(res["Ik_max_u_ochrany_A"]), 241.5 / hypot(0.15, 0.04), places=4)
        zap = pro_spis(str(id_spisu("zaporny")))
        self.assertIsNone(zap["vybrany_mm2"])
        self.assertEqual(zap["varianty"][2]["chyby"], ["ubytek","porucha_L_PE","zkrat_L_N"])
        self.assertIsNone(pro_spis("cizi-spis"))

    def test_rovnost_a_tesne_prekroceni(self):
        self.p.update(U0_V="100",zatizeni_A="10",delka_m="100")
        for k,v in self.p["zdroj"].items():
            v.update(R="0.1" if "min" in k else "0.3",X="0")
        m = self.registr[0]
        m.update(max_ubytek_pct="7",napeti_min_pomer="1",napeti_max_pomer="1")
        m["ulozeni"]["trasa-TEST"] = "0.5"
        ochrana = m["ochrany"]["J-TEST"]
        ochrana.update(jmenovity_A="10",vypinaci_schopnost_A="1000")
        vodic = m["vodice"][1]
        m["vodice"] = [vodic]
        vodic.update(zatizitelnost_A="20",R_L_ohm_km="3.5",R_N_ohm_km="3.5",R_PE_ohm_km="3.5",X_ohm_km="0")
        res = posud(self.p,self.registr)
        self.assertEqual(res["vybrany_mm2"],"2.5")
        self.assertEqual(res["varianty"][0]["Id_LPE_min_A"],"100")
        self.p["delka_m"] = "100.0001"
        v = posud(self.p,self.registr)["varianty"][0]
        self.assertEqual(v["dU_V"],"7")
        self.assertEqual(v["chyby"],["ubytek","porucha_L_PE","zkrat_L_N"])
        self.p["delka_m"] = "100"
        self.p["zdroj"]["LPE_min_ohm"]["R"] = "0.0999"
        self.assertEqual(posud(self.p,self.registr)["varianty"][0]["chyby"],["vypinaci_schopnost"])

    def test_zmena_poradi_a_oddeleni_smycek(self):
        self.registr[0]["vodice"].reverse()
        self.assertEqual(posud(self.p,self.registr)["vybrany_mm2"],"2.5")
        for druh,chyba in (("LN","zkrat_L_N"),("LPE","porucha_L_PE")):
            p = deepcopy(self.p)
            p["zdroj"][druh+"_max_ohm"]["R"] = "3"
            self.assertEqual(posud(p,self.registr)["varianty"][1]["chyby"],[chyba])

    def test_neplatne_vstupy(self):
        for zmena in ({"ucel":"ostry"},{"model":"trifazovy"},{"den":"2027-02-01"},
                      {"U0_V":"0"},{"zatizeni_A":"NaN"},{"delka_m":"-1"}):
            with self.subTest(zmena=zmena), self.assertRaises(ValueError):
                posud({**self.p,**zmena},self.registr)
        for registr in ([],self.registr*2):
            with self.assertRaises(ValueError):
                posud(self.p,registr)
        for k,v in (("LN_min_ohm",{"R":"1","X":"0.1"}),("LPE_min_ohm",{"R":"0","X":"0"})):
            with self.subTest(k=k), self.assertRaises(ValueError):
                posud({**self.p,"zdroj":{**self.p["zdroj"],k:v}},self.registr)
        m = self.registr[0]
        for zmena in ({"max_ubytek_pct":"110"},{"napeti_min_pomer":"1.1"},
                      {"vodice":[]},{"vodice":m["vodice"]*2}):
            with self.subTest(zmena=zmena), self.assertRaises(ValueError):
                posud(self.p,[{**m,**zmena}])
