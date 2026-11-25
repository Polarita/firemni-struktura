"""Kontroly převzetí stránek, otisku a dostupnosti zbytku karty spisu."""
from copy import deepcopy
from hashlib import sha1
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"metadata-schema-kernel"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE/"revize"))
from spisy_rz import id_spisu
import metodiky_vault
import registr_metodik as registr
from projektove_vypocty import cast_karty


def git_oid(raw):
    return sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class RegistrTest(unittest.TestCase):
    def setUp(self):
        rev, ocekavane = registr.vydani()
        self.pages = {p:{"text":txt,"revize":"a"*40,"objekt":git_oid(txt.encode())}
                      for p, (_, txt) in ocekavane.items()}
        self.balik = {"vydani":rev, "stranky":self.pages}
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for modul in (registr, metodiky_vault):
            mock = patch.object(modul,"ULOZISTE",self.root)
            mock.start()
            self.addCleanup(mock.stop)
        self.case = str(id_spisu("kladny"))

    def test_opakovani_a_zneni(self):
        with patch("builtins.print"):
            metodiky_vault.prijmi(self.balik)
            metodiky_vault.prijmi(self.balik)
        karta = cast_karty(self.case)
        self.assertEqual(karta["vedeni"]["vybrany_mm2"],"2.5")
        for model in karta.values():
            zdroj = model["zdroj_metodiky"]
            self.assertEqual(zdroj["text"],self.pages[zdroj["cesta"]]["text"])
            self.assertEqual(zdroj["objekt"],git_oid(zdroj["text"].encode()))
        # Jiný původ téhož obsahu vyžaduje řešit kolizi vydání.
        self.pages[next(iter(self.pages))]["revize"] = "b"*40
        with self.assertRaises(ValueError):
            metodiky_vault.prijmi(self.balik)
        self.assertEqual(cast_karty(self.case),karta)

    def test_poskozena_nebo_chybejici_kopie(self):
        self.assertEqual(set(cast_karty(self.case)),{"chyba_metodik"})
        self.assertEqual(cast_karty("cizi"),{})
        with patch("builtins.print"):
            metodiky_vault.prijmi(self.balik)
        file = self.root/self.balik["vydani"]/"registr.json"
        data = json.loads(file.read_bytes())
        data["registr"]["stranky"][next(iter(self.pages))]["revize"] = "f"*40
        file.write_text(json.dumps(data))
        self.assertEqual(set(cast_karty(self.case)),{"chyba_metodik"})

    def test_chybny_obsah_a_verze(self):
        p = next(iter(self.pages))
        for delta in ({"objekt":"0"*40}, {"revize":"HEAD"}, {"text":"nahrazený obsah"}):
            data = deepcopy(self.balik)
            data["stranky"][p].update(delta)
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                registr.over(data)
        for data in ({**self.balik,"vydani":"0"*64},{**self.balik,"stranky":{}}):
            with self.assertRaises(ValueError):
                registr.over(data)
