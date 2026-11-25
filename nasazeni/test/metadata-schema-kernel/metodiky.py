"""Sdílené načtení verzovaných vstupů projektových výpočtů TEST."""
from datetime import date
from decimal import Decimal
from functools import cache
import json
from pathlib import Path
import re

from model import unique


SOUBORY = Path(__file__).resolve().parent


@cache
def nacti(soubor):
    # Každá instalace spouští nový proces z adresáře vydání určeného obsahem.
    return json.loads((SOUBORY / soubor).read_bytes(), object_pairs_hook=unique)


def platna(projekt, metodiky, druh):
    den = date.fromisoformat(projekt["den"])
    shody = [m for m in metodiky if m["model"] == projekt["model"] == druh
             and m["ucel"] == projekt["ucel"] == "simulace"
             and date.fromisoformat(m["od"]) <= den <= date.fromisoformat(m["do"])]
    if len(shody) != 1:
        raise ValueError("Pro datum, účel a model musí být platná právě jedna metodika.")
    return shody[0]


def hodnota(udaj):
    if not isinstance(udaj, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,6})(?:\.[0-9]{1,4})?", udaj):
        raise ValueError("Očekávána konečná nezáporná desetinná hodnota.")
    return Decimal(udaj)


def text(cislo):
    return format(cislo.normalize(), "f")
