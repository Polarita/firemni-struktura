from array import array
import importlib.util
import math
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "nasazeni/test/telefon/hovor.py"
spec = importlib.util.spec_from_file_location("telefon_test", source)
telefon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(telefon)


def ton(hz, delka=1):
    return array("h", (round(8500 * math.sin(2 * math.pi * hz * i / telefon.VZORKY))
                       for i in range(int(delka * telefon.VZORKY))))


class SmerovyZaznam(unittest.TestCase):
    def test_ton_po_uvodnim_tichu(self):
        for hz in (440, 880):
            with self.subTest(hz=hz):
                telefon.over_ton(array("h", [0]) * 4000 + ton(hz), hz)

    def test_zameneny_kanal_ticho_a_kratky_ton(self):
        for vzorky in (ton(440), array("h", [0]) * telefon.VZORKY, ton(880, 0.5)):
            with self.assertRaises(ValueError):
                telefon.over_ton(vzorky, 880)
