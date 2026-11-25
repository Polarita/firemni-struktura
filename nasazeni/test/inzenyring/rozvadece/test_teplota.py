from copy import deepcopy
import json
from pathlib import Path

import pytest

from teplota import posud

HERE = Path(__file__).resolve().parent
REGISTR = json.loads((HERE / "metodika-test.json").read_bytes())
OSAZENI = json.loads((HERE / "osazeni-test.json").read_bytes())
KUSOVNIK = [p["oznaceni"] for p in OSAZENI["pristroje"]]


def test_interpolace():
    assert posud(REGISTR, OSAZENI, KUSOVNIK) == {
        "ztrata_W":"96", "stred_K":"18", "vrch_K":"24", "uvnitr_C":"59", "mez_C":"60"}


@pytest.mark.parametrize("path,value", [
    (("rozsah",), "jiný typ"), (("den_posouzeni",), "2030-01-01"),
    (("pristroje",), []), (("pristroje",0,"oznaceni"), "-FA1"),
    (("pristroje",0,"oznaceni"), "-QS2"), (("pristroje",0,"ztrata_W"), "-1"),
    (("pristroje",0,"ztrata_W"), "150"), (("pristroje",0,"ztrata_W"), "NaN"),
    (("pristroje",0,"ztrata_W"), 5), (("okoli_C",), "37")])
def test_chybne_osazeni(path, value):
    vzor = deepcopy(OSAZENI)
    pole = vzor
    for key in path[:-1]:
        pole = pole[key]
    pole[path[-1]] = value
    with pytest.raises(ValueError):
        posud(REGISTR, vzor, KUSOVNIK)


@pytest.mark.parametrize("key,value", [
    ("jednotky",["kW","K","K"]), ("pravidla", ["jiná pravidla"]),
    ("krivka_W_K_stred_K_vrch", []),
    ("krivka_W_K_stred_K_vrch", [["0","0","1"],["80","15","20"]]),
    ("krivka_W_K_stred_K_vrch", [["0","0","0"],["80","20"]]),
    ("krivka_W_K_stred_K_vrch", [["0","0","0"],["80","20","15"]]),
    ("krivka_W_K_stred_K_vrch", [["0","0","0"],["10","1","2"],["5","1","2"]]),
    ("krivka_W_K_stred_K_vrch", [["0","0","0"],["10","1","2"],["11","0","2"]]),
    ("krivka_W_K_stred_K_vrch", [["0","0","0"],["10","1","2"],["11","1","1"]])])
def test_neplatna_metodika(key, value):
    with pytest.raises(ValueError):
        posud({**REGISTR,key:value}, OSAZENI, KUSOVNIK)
