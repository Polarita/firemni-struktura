from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

finance = Path(__file__).resolve().parents[1] / "nasazeni/test/finance"
spec = importlib.util.spec_from_file_location("provize", finance / "provize.py")
provize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provize)


class Provize(unittest.TestCase):
    def setUp(self):
        self.podminky = json.loads((finance / "provize-TEST.json").read_bytes())
        self.uhrady = json.loads((finance / "vypis-TEST.json").read_bytes())["uol"]

    def sestav(self):
        shody = {(r["banka"], r["pohyb"]): r["doklad"] for r in self.uhrady}
        return provize.sestav(self.podminky, self.uhrady, shody)

    def test_dalsi_mesic_castecna_uhrada_a_vratka(self):
        priklad = self.uhrady[0]
        self.uhrady = [
            priklad | {"pohyb": "cast", "castka": "121.00", "uhrazeny_pausal_bez_dph": "100.00"},
            priklad | {"pohyb": "vratka", "castka": "-121.00", "uhrazeny_pausal_bez_dph": "-100.00"},
            priklad | {"pohyb": "dalsi-mesic", "obdobi": "2026-12-01"},
        ]
        mrr = [(r["obdobi"], r["provize"]) for r in self.sestav() if r["druh"] == "mrr"]
        self.assertEqual(mrr, [("2026-11-01", "10.00"), ("2026-11-01", "-10.00"), ("2026-12-01", "152.07")])

    def test_nevznika_nezaslouzena_odmena(self):
        self.podminky["realizace"][0]["predano"] = False
        self.podminky["pausaly"]["TEST-PAUSAL-B"]["certifikovan"] = False
        self.uhrady = self.uhrady[1:]
        self.assertEqual(self.sestav(), [])

    def test_chybna_sazba_mena_nebo_zaklad_zastavi_import(self):
        puvodni = deepcopy(self.uhrady[0])
        for zmena in ({"mena": "EUR"}, {"uhrazeny_pausal_bez_dph": "1840.11"},
                      {"uhrazeny_pausal_bez_dph": "-1.00"}, {"uhrazeny_pausal_bez_dph": "1.001"}):
            with self.subTest(zmena=zmena), self.assertRaises(ValueError):
                self.uhrady[0] = puvodni | zmena
                self.sestav()
        self.uhrady[0] = puvodni
        for sazba in ("9.99", "15.01"):
            with self.subTest(sazba=sazba), self.assertRaises(ValueError):
                self.podminky["pausaly"]["TEST-PAUSAL-A"]["sazba_pct"] = sazba
                self.sestav()

    def test_neprirazena_platba_uol_neprojde(self):
        with self.assertRaisesRegex(ValueError, "výpisu"):
            provize.sestav(self.podminky, self.uhrady, {})
