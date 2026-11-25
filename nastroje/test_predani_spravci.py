import importlib.util
from pathlib import Path
import tempfile
import unittest

MODUL = Path(__file__).resolve().parents[1] / "nasazeni/test/predani.py"
spec = importlib.util.spec_from_file_location("predani_spravci", MODUL)
predani = importlib.util.module_from_spec(spec)
spec.loader.exec_module(predani)


class PredaniSpravci(unittest.TestCase):
    def setUp(self):
        adresar = tempfile.TemporaryDirectory()
        self.addCleanup(adresar.cleanup)
        self.root = Path(adresar.name)
        self.rev = "a" * 40
        self.dns = "portal.example.test"

    def doklady(self, rev):
        for blok, nazev, pripona, _ in predani.DOKLADY:
            cesta = self.root / f"blok-{blok}" / f"{nazev}-{rev}.{pripona}"
            cesta.parent.mkdir(exist_ok=True)
            cesta.write_bytes(b"never-copy-receipt-content")
        return cesta

    def test_starsi_doklady_nenahradi_aktualni(self):
        self.doklady("b" * 40)
        obsah, chybi = predani.sestav(self.root, self.rev, self.dns)
        self.assertEqual(len(chybi), len(predani.DOKLADY))
        self.assertIn("Čeká se", obsah)
        with self.assertRaises(ValueError):
            predani.uloz(self.root, self.rev, self.dns)
        self.assertFalse(list(self.root.rglob("predani-spravci-*")))

    def test_zprava_odpovida_nahledu_a_neobsahuje_data(self):
        self.doklady(self.rev)
        obsah, chybi = predani.sestav(self.root, self.rev, self.dns)
        self.assertFalse(chybi)
        self.assertNotIn("never-copy", obsah)
        for _ in range(2):
            self.assertEqual(predani.uloz(self.root, self.rev, self.dns).read_text(), obsah)

    def test_prazdny_soubor_a_odkaz(self):
        cesta = self.doklady(self.rev)
        cesta.write_bytes(b"")
        with self.assertRaises(ValueError):
            predani.uloz(self.root, self.rev, self.dns)
        cesta.unlink()
        cesta.symlink_to(__file__)
        with self.assertRaises(OSError):
            predani.uloz(self.root, self.rev, self.dns)
