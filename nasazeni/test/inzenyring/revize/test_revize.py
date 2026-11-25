import copy
import csv
from datetime import date
import json
from pathlib import Path
from unittest import TestCase
from tempfile import TemporaryDirectory

from import_mereni import LIMIT, nacti
from posouzeni import posud, dukazy, vyhodnot

ROOT = Path(__file__).with_name("vzor")
DAY = date(2026, 11, 20)


class Revize(TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "plan.json").read_bytes())
        self.rows = nacti((ROOT / "kladny.json").read_bytes(), "json")
        self.docs = dukazy(ROOT / "doklady", self.plan["otisky_dokladu"])

    def test_tri_formaty_a_oba_vyroky(self):
        for variant in ("kladny", "zaporny"):
            results = [vyhodnot(self.plan, ROOT / "doklady", nacti((ROOT / (variant+"."+fmt)).read_bytes(), fmt), DAY)
                       for fmt in ("json", "csv", "xml")]
            self.assertEqual(results[0], results[1])
            self.assertEqual(results[1], results[2])
            self.assertEqual(results[0]["stav"], "navrh-"+variant)
            self.assertEqual(results[0]["zavady"], ["M1"] if variant == "zaporny" else [])
            self.assertFalse(results[0]["predani_do_provozu"])

    def test_neplatne_soubory(self):
        for raw, fmt in ((b"", "json"), (b"x"*(LIMIT+1), "csv"), (b"{}", "json"), (b"[]","json"),
                         (b'{"bod":1,"bod":2}',"json"), (b'[["M1"]]',"json"), (b"none","pdf"),
                         (b"a,b\n1,2\n","csv"), (b"<mereni><x","xml"), (b"<mereni a='1'/>","xml"),
                         (b"<!DOCTYPE x><mereni/>","xml"), (b"<mereni><x/></mereni>","xml")):
            with self.subTest(fmt=fmt, raw=raw[:40]), self.assertRaises((ValueError, csv.Error)):
                nacti(raw, fmt)
        self.rows[0]["hodnota"] = 0
        with self.assertRaises(ValueError):
            nacti(json.dumps(self.rows).encode(), "json")

    def test_odmitnuta_mereni(self):
        for field, value in (("projekt","jiny"),("den","2026-11-19"),("den","20261120"),("bod","M2"),
                             ("hodnota","NaN"),("jednotka","V"),("pristroj","MER-X")):
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(vyhodnot(self.plan, ROOT/"doklady", rows, DAY)["stav"], "FAIL_CLOSED")
        for rows in ([], self.rows[:1], self.rows+[self.rows[1]]):
            self.assertEqual(vyhodnot(self.plan, ROOT/"doklady", rows, DAY)["stav"], "FAIL_CLOSED")

    def test_podklady(self):
        for key, field, value in (("KAL-TEST-01","do","2026-11-19"),("PAS-TEST-01","projekt","RZ-JINY"),
                                 ("DEN-TEST-01","uzavren", False),("DTM-TEST-01","den","2026-11-21"),
                                 ("STIT-TEST-01","druh","pas"),("KAL-TEST-01","pristroj","MER-X")):
            docs = copy.deepcopy(self.docs)
            docs[key][field] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                posud(self.plan, docs, self.rows, DAY)
        with self.assertRaises(ValueError):
            posud(self.plan, self.docs, self.rows, date(2026,11,19))
        self.plan["novy_rozvadec"] = "ano"
        self.assertEqual(vyhodnot(self.plan,ROOT/"doklady",self.rows,DAY)["stav"], "FAIL_CLOSED")
        for flag in ("novy_rozvadec", "stavebni_denik", "vykop"):
            self.plan[flag] = False
        self.plan["prilohy"] = {}
        self.assertEqual(posud(self.plan,self.docs,self.rows,DAY)["stav"], "navrh-kladny")

    def test_identita_dokladu(self):
        with TemporaryDirectory() as tmp:
            raw = b'{"id":"KAL-TEST-02","rezim":"TEST"}'
            from hashlib import sha256
            (Path(tmp)/"KAL-TEST-01.json").write_bytes(raw)
            for key, digest in (("../X","a"*64), ("KAL-TEST-01","0"*64), ("KAL-TEST-01",sha256(raw).hexdigest())):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    dukazy(Path(tmp),{key:digest})
            self.assertEqual(vyhodnot(self.plan,Path(tmp),self.rows,DAY)["stav"],"FAIL_CLOSED")
