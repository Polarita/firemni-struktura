import json
import os
import unittest
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from lxml.etree import DocumentInvalid
from openpyxl import load_workbook

from nabidka import MARK, over_xml, polozky, sestav, souhrn, xml_bytes
from sesit import do_xc4, do_xlsx


class Rozpocet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = Path(os.environ["POLARITA_XC4_SCHEMA"])
        cls.raw = xml_bytes(sestav(json.loads(Path(__file__).with_name("vykaz-test.json").read_bytes())))
        cls.book = do_xlsx(cls.raw, cls.schema)

    def zmena(self, edit, book=None):
        wb = load_workbook(BytesIO(book or self.book))
        edit(wb["Položky"])
        stream = BytesIO()
        wb.save(stream)
        return do_xc4(stream.getvalue(), self.schema)

    def test_presny_navrat(self):
        self.assertEqual(self.raw, do_xc4(self.book, self.schema))

    def test_zmena_ceny(self):
        result = self.zmena(lambda s: setattr(s["H2"], "value", 41.25))
        self.assertEqual(souhrn(polozky(over_xml(result, self.schema))), Decimal("3539.53"))

    def test_ochrana(self):
        for cell, value in (("G2", "=1+1"), ("A2", "P02"), ("B2", "CIZI"), ("I2", 2), ("I2", True),
                            ("H2", "0.12345"), ("G2", None), ("I2", 10)):
            with self.subTest(cell=cell, value=value), self.assertRaises(ValueError):
                self.zmena(lambda s: setattr(s[cell], "value", value))
        with self.assertRaises(ValueError):
            self.zmena(lambda s: s.delete_rows(2))

    def test_presna_cena(self):
        root = over_xml(self.raw, self.schema)
        polozky(root)["P01"]["xml"].find("joc").text = "123456789012345.6789"
        raw = xml_bytes(root)
        self.assertEqual(raw, do_xc4(do_xlsx(raw, self.schema), self.schema))

    def test_externi_vykaz(self):
        root = over_xml(self.raw, self.schema)
        item = polozky(root)["P01"]["xml"]
        item.remove(item.find("popis"))
        item.find("nazev").text = "=TEXT"
        raw = xml_bytes(root)
        result = self.zmena(lambda s: setattr(s["I2"], "value", 1), do_xlsx(raw, self.schema))
        row = polozky(over_xml(result, self.schema))["P01"]
        self.assertEqual(row["nazev"], "=TEXT")
        self.assertEqual(row["xml"].findtext("popis"), MARK+"1")

    def test_xml(self):
        with self.assertRaises(DocumentInvalid):
            do_xlsx(b"<XC4/>", self.schema)
        with self.assertRaisesRegex(ValueError, "DTD"):
            do_xlsx(self.raw.replace(b"<XC4>", b"<!DOCTYPE XC4><XC4>"), self.schema)


if __name__ == "__main__":
    unittest.main()
