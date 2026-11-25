"""Revize v režimu vydání přijímá pouze pas konkrétního kusu a spisu."""
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from priprav import priprav

ROOT = Path(__file__).with_name("vzor")
sys.path.insert(0, str(ROOT.parents[1] / "rozvadece"))
import pas
from spisy_rz import id_spisu

CASE = "POL-2026-00008"
SERIAL = "RZ-2026-00002"
HOST = "reditelstvi.test.ts.net"
PDF = b"model zdroje binarniho souboru"
HASH = hashlib.sha256(PDF).hexdigest()
INFO = {"case_id":CASE, "vyrobni_cislo":SERIAL, "kniha":f"https://{HOST}/lhutnik-test/spisy?spis={CASE}&oddil=kniha",
        "stav":"navrh-test", "strany":5, "pdf_sha256":HASH, "predani_do_provozu":False}


def vydani(info, pdf=PDF):
    raw = json.dumps(info).encode()
    sums = (HASH+"  vyrobni-pas.pdf\n"+hashlib.sha256(raw).hexdigest()+"  prehled.json\n").encode()
    return {"current":hashlib.sha256(sums).hexdigest().encode(), "SHA256SUMS":sums,
            "vyrobni-pas.pdf":pdf, "prehled.json":raw}


def nacti(files):
    def read(vm, *args):
        assert vm == "postgres-test" and args[:4] == ("runuser", "-u", "pol_metadata_read", "--")
        return files[Path(args[-1]).name]
    with patch.object(pas,"rozvadec_spisu",return_value=(CASE,SERIAL)), patch.object(pas,"run",side_effect=read), \
            patch.object(pas,"over_pdf",return_value="2026-11-25") as over_pdf:
        info = pas.nacti_vydani(str(id_spisu("kladny")), HOST)
        over_pdf.assert_called_once_with(PDF,SERIAL,CASE,INFO["kniha"])
        return info


def sestav(info):
    return priprav(ROOT/"kladny.json", ROOT/"plan.json", CASE, date(2026,11,25), pas=info)


def test_puvod_a_otisk_v_obou_dokladech():
    info = nacti(vydani(INFO))
    model = sestav(info)
    assert model["puvod_podkladu"] == "vydany-pas-ve-spisu" and model["pas"] == info
    assert model["doklady_sha256"]["PAS-TEST-01"] == model["doklady_sha256"]["STIT-TEST-01"] == HASH
    assert model["predani_do_provozu"] is False


@pytest.mark.parametrize("change", [{"case_id":"POL-2026-00009"}, {"vyrobni_cislo":"RZ-2026-00001"},
                                    {"kniha":"https://example.invalid/"}, {"strany":4}, {"predani_do_provozu":True}])
def test_cizi_nebo_neuplne_vydani(change):
    with pytest.raises(ValueError):
        nacti(vydani({**INFO, **change}))


def test_chybejici_pozmenene_a_pozdni():
    for name in ("current","SHA256SUMS","vyrobni-pas.pdf","prehled.json"):
        files = vydani(INFO)
        del files[name]
        with pytest.raises(KeyError):
            nacti(files)
    with pytest.raises(ValueError):
        nacti(vydani(INFO,pdf=PDF+b"x"))
    with pytest.raises(ValueError):
        sestav({**INFO,"den":"2026-11-26"})
    with pytest.raises(ValueError):
        sestav({**INFO,"case_id":"POL-2026-00009"})
