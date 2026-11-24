"""Nastaví klienta týmového chatu prostřednictvím společné správy realmu."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[1] / "identita/sluzba_oidc.py"), run_name="__main__")
