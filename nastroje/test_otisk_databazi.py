from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / "nasazeni/test/databaze/obnova.py"
spec = spec_from_file_location("obnova_test", source)
obnova = module_from_spec(spec)
spec.loader.exec_module(obnova)


class OtiskDatabazi(unittest.TestCase):
    def test_opakuje_jen_cteni_po_vypadku_incus(self):
        otisk = bytes(range(32))
        odpovedi = [subprocess.CompletedProcess([], 1, b""), subprocess.TimeoutExpired([], 300),
                    subprocess.CompletedProcess([], 0, otisk)]
        with patch.object(obnova.subprocess, "run", side_effect=odpovedi) as beh, patch.object(obnova.time, "sleep"):
            self.assertEqual(obnova.proof("obnova-pg-test", "obnova_test"), otisk)
        self.assertEqual(beh.call_count, 3)
        self.assertTrue(all(volani == beh.call_args_list[0] for volani in beh.call_args_list))
        self.assertIn("otisk", beh.call_args.kwargs["input"].decode())

    def test_neplatny_obsah_nebo_neshoda_se_neopakuje(self):
        for kod, data in [(0, b"kratky"), (65, b"")]:
            with self.subTest(kod=kod), patch.object(obnova.subprocess, "run", return_value=subprocess.CompletedProcess([], kod, data)) as beh:
                with self.assertRaises(RuntimeError):
                    obnova.proof("obnova-pg-test", "obnova_test")
                beh.assert_called_once()
