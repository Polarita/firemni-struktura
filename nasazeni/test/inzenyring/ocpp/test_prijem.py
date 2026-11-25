import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from prijem import odpoved, priprav
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"metadata-schema-kernel"))
import ocpp_cteni

schema = {"required":["connectorStatus","timestamp","evseId","connectorId"],
          "definitions":{"ConnectorStatusEnumType":{"enum":["Available","Faulted"]}}}
sample = {"connectorStatus":"Available","timestamp":"2026-11-25T08:12:00Z","evseId":1,"connectorId":1}


def send(db, uid, values, case="POL-2026-00008"):
    return odpoved(json.dumps([2,uid,"StatusNotification",values]),db,"EV-TEST-01",case,schema)


def test_readonly_replay_and_order(tmp_path):
    db = tmp_path/"telemetrie.sqlite"
    priprav(db)
    assert send(db,"new",sample) == send(db,"new",sample) == [3,"new",{}]
    assert send(db,"old",{**sample,"timestamp":"2026-11-25T08:00:00Z","connectorStatus":"Faulted"}) == [3,"old",{}]
    assert send(db,"new",{**sample,"connectorId":2})[0] == 4
    assert send(db,"new",sample,case="POL-2026-00009")[0] == 4
    with patch.object(ocpp_cteni, "DB", db):
        assert ocpp_cteni.stav("POL-2026-00008") == [{"stanice":"EV-TEST-01","evse":1,"konektor":1,
            "stav":"Available","pocet":2,"cas":"2026-11-25T08:12:00.000000+00:00"}]
        assert ocpp_cteni.stav("POL-2026-00009") == []


@pytest.mark.parametrize("change",[{"connectorStatus":"neznámý"},{"timestamp":"2026-02-30T10:00:00Z"},
    {"timestamp":"08:12"},{"evseId":True},{"connectorId":-1},{"x":12},{"customData":{}},{"customData":None}])
def test_chybne_oznameni(tmp_path, change):
    db = tmp_path/"telemetrie.sqlite"
    priprav(db)
    assert send(db,"test",{**sample,**change})[:3] == [4,"test","PropertyConstraintViolation"]
    with patch.object(ocpp_cteni,"DB",db):
        assert ocpp_cteni.stav("POL-2026-00008") == []


@pytest.mark.parametrize("wire",[b"{}", "[2.0,\"x\",\"StatusNotification\",{}]", "[2,\"\",\"x\",{}]",
    '[2,"ID","StatusNotification",{"evseId":1,"evseId":2}]'])
def test_poruchy_obalky(tmp_path, wire):
    with pytest.raises(ValueError):
        odpoved(wire,tmp_path/"telemetrie.sqlite","EV-TEST-01","POL-2026-00008",schema)
