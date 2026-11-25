import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "metadata-schema-kernel"))
from vykop import vyhodnot


@pytest.fixture
def stav():
    vzor = HERE / "vzor"
    def load(name):
        return json.loads((vzor / (name + ".json")).read_bytes())
    docs = load("doklady")
    return {"revize":docs["revize"], "doklady":docs, "projekt":load("trasa"), "metodika":load("metodika"),
            "den":"2026-11-25", "archiv":{docs["mapa"]:1, docs["vyjadreni"]["SIT-TEST-A"]["sha256"]:2}}


@pytest.mark.parametrize("path,value", [
    (("revize",), "f" * 64), (("den",), "2036-01-01"), (("metodika","ucel"),"ostry-provoz"),
    (("projekt","spravci"),[]), (("projekt","body_mm"),[[0,0],[0,0]]),
    (("doklady","mapa"),"0" * 64), (("doklady","vyjadreni"),{}), (("archiv",),{}),
    (("doklady","vyjadreni","SIT-TEST-A","plati_od"),"2026-11-26"),
    (("doklady","vyjadreni","SIT-TEST-A","plati_do"),"2026-11-24"),
    (("doklady","vyjadreni","SIT-TEST-A","souhlas"),False),
    (("doklady","vyjadreni","SIT-TEST-A","revize"),"0" * 64),
    (("projekt","useky",0,"do"),2), (("projekt","useky",0,"stret"),"chyba"),
    (("projekt","useky",0,"kryti_mm"),"849.999"), (("projekt","useky",0,"kryti_mm"),"NaN"),
    (("projekt","useky",1,"odstup_mm"),"499.999"), (("projekt","useky",0,"odstup_mm"),"399.999"),
    (("projekt","useky"),[]), (("metodika","plati_od"),None),
])
def test_odmitnuti(stav, path, value):
    parent = stav
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    assert vyhodnot(stav)


def test_shoda_na_hranici(stav):
    for section in stav["projekt"]["useky"]:
        section["kryti_mm"] = stav["metodika"]["kryti_mm"]
        section["odstup_mm"] = stav["metodika"]["odstup_mm"][section["stret"]]
    for day in ("2025-01-01","2035-12-31"):
        stav["den"] = day
        assert vyhodnot(stav) == []


def test_bez_stretu(stav):
    for section in stav["projekt"]["useky"]:
        section["stret"] = "bez-stretu"
        del section["odstup_mm"]
    assert vyhodnot(stav) == []


def test_mapa_nenahrazuje_vyjadreni(stav):
    stav["doklady"]["vyjadreni"]["SIT-TEST-A"]["sha256"] = stav["doklady"]["mapa"]
    assert vyhodnot(stav)
