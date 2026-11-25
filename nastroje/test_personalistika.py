from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "nasazeni/test/personalistika/pracovnici.py"
spec = importlib.util.spec_from_file_location("pracovnici_test", source)
pracovnici = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pracovnici)


class ZkouskaNastupu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads((pracovnici.S2 / "eval_suite_polarita_extended.json").read_bytes())
        cls.nastupy = [s for s in data["scenarios"] if s["event"]["type"] == "worker_release"]

    def test_prehled_zachova_kazdy_scenar_bez_osobnich_podkladu(self):
        vysledky = pracovnici.vyhodnot(self.nastupy)
        self.assertEqual({p["scenar"] for p in vysledky}, {s["id"] for s in self.nastupy})
        self.assertEqual(len({p["person_no"] for p in vysledky}), len(self.nastupy))
        for p in vysledky:
            self.assertEqual(set(p), {"scenar", "person_no", "rozhodnuti", "duvod", "otisk"})

    def test_predloha_se_musi_shodovat_i_v_akcich(self):
        scenare = deepcopy(self.nastupy)
        scenare[0]["expected"]["required_actions"].append("release_to_calendar")
        with self.assertRaisesRegex(ValueError, scenare[0]["id"]):
            pracovnici.vyhodnot(scenare)
