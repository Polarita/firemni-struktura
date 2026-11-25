"""Převzetí starší sady a opětovné ověření při nedostupném GitHubu."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nasazeni/test"))
import vydani


class PrevzetiVydani(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.target = self.base / "tisk"
        self.target.mkdir()
        self.commit = "a" * 40
        self.tag = json.loads(Path(__file__).with_name("kanon.json").read_bytes())["release_tag"]
        self.hashes = {}
        for name in sorted(vydani.DOKUMENTY | {"konfigurator.html", "manifesty-S1.zip", "formular.pdf"}):
            file = self.target / name
            file.write_bytes(name.encode())
            self.hashes[name] = vydani.otisk(file)
        manifest = self.target / "SHA256SUMS"
        manifest.write_text("".join(f"{h}  {name}\n" for name, h in self.hashes.items()))
        self.hashes[manifest.name] = vydani.otisk(manifest)

    def test_migrace_a_offline_kontrola(self):
        vydani.mistni_vydani(self.base, self.commit, None, self.hashes)
        self.assertFalse((self.base / "tisk-github.json").exists())
        self.assertIsNone(vydani.mistni_vydani(self.base, self.commit, self.tag))
        vydani.mistni_vydani(self.base, self.commit, self.tag, self.hashes)
        self.assertEqual(self.hashes, vydani.mistni_vydani(self.base, self.commit, self.tag))
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, "b" * 40, self.tag)
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, self.commit, self.tag + ".1")

    def test_podvrzena_priloha_nebo_manifest(self):
        vydani.mistni_vydani(self.base, self.commit, self.tag, self.hashes)
        (self.target / "formular.pdf").write_text("změněný formulář")
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, self.commit, self.tag)
        (self.target / "formular.pdf").write_text("formular.pdf")
        (self.target / "SHA256SUMS").write_text("")
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, self.commit, self.tag)

    def test_zmena_sady_a_opakovane_prevzeti(self):
        vydani.mistni_vydani(self.base, self.commit, self.tag, self.hashes)
        receipt = self.base / "tisk-github.json"
        before = json.loads(receipt.read_bytes())
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, self.commit, self.tag, self.hashes | {"formular.pdf": "b" * 64})
        self.assertEqual(before, json.loads(receipt.read_bytes()))
        (self.target / "neocekavany.pdf").touch()
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, self.commit, self.tag)

    def test_nedokonceny_prijem_nevytvori_potvrzeni(self):
        (self.target / "formular.pdf").unlink()
        with self.assertRaises(ValueError):
            vydani.mistni_vydani(self.base, self.commit, self.tag, self.hashes)
        self.assertFalse((self.base / "tisk-github.json").exists())
