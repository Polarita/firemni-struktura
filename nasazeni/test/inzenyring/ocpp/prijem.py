"""Místní příjem OCPP-J 2.1 pro čtecí diagnostiku registrovaných stanic."""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
DB = Path("/var/lib/polarita-ocpp-test/telemetrie.sqlite")
SOCKET = "/run/polarita-ocpp-test/prijem.sock"
PROTOCOL = "ocpp2.1"


def priprav(db):
    with closing(sqlite3.connect(db)) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS udalost(
          stanice TEXT NOT NULL, zprava TEXT NOT NULL, spis TEXT NOT NULL,
          evse INTEGER NOT NULL, konektor INTEGER NOT NULL, stav TEXT NOT NULL,
          cas TEXT NOT NULL, otisk TEXT NOT NULL, PRIMARY KEY(stanice,zprava));
        CREATE INDEX IF NOT EXISTS udalost_spis ON udalost(spis,stanice,evse,konektor,cas DESC);
        """)


def jednoznacne(items):
    d = dict(items)
    if len(d) != len(items):
        raise ValueError("duplicitní klíč")
    return d


def uloz(db, station, case, message_id, payload, schema):
    optional = set(payload) - set(schema["required"])
    if (optional - {"customData"} or not set(schema["required"]) <= payload.keys() or
            payload["connectorStatus"] not in schema["definitions"]["ConnectorStatusEnumType"]["enum"]):
        raise ValueError("pole oznámení nebo stav konektoru")
    if "customData" in payload:
        extra = payload["customData"]
        if not isinstance(extra,dict) or not isinstance(extra.get("vendorId"),str) or not 1 <= len(extra["vendorId"]) <= 255:
            raise ValueError("identifikace rozšíření")
    for key in ("connectorId","evseId"):
        if type(payload[key]) is not int or not 1 <= payload[key] <= 2147483647:
            raise ValueError("identifikace fyzického konektoru")
    stamp = payload["timestamp"]
    if not isinstance(stamp,str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",stamp):
        raise ValueError("čas oznámení")
    stamp = datetime.fromisoformat(stamp.replace("Z","+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds")
    digest = hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False,separators=(",",":")).encode()).hexdigest()
    with closing(sqlite3.connect(db, timeout=5)) as con, con:
        con.execute("""INSERT INTO udalost VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(stanice,zprava) DO NOTHING""",
                    (station,message_id,case,payload["evseId"],payload["connectorId"],payload["connectorStatus"],stamp,digest))
        previous = con.execute("SELECT otisk,spis FROM udalost WHERE stanice=? AND zprava=?", (station,message_id)).fetchone()
        if previous != (digest,case):
            raise ValueError("změněný obsah opakované zprávy")


def odpoved(wire, db, station, case, schema):
    if not isinstance(wire,str):
        raise ValueError("Očekáván textový rámec.")
    frame = json.loads(wire,object_pairs_hook=jednoznacne)
    if (not isinstance(frame,list) or len(frame)!=4 or type(frame[0]) is not int or frame[0]!=2 or
            not isinstance(frame[1],str) or not 1 <= len(frame[1]) <= 36 or not isinstance(frame[2],str)):
        raise ValueError("Chybná obálka OCPP CALL.")
    _, request, action, payload = frame
    if action != "StatusNotification":
        return [4,request,"NotSupported","Příjem přijímá pouze stav konektoru.",{}]
    try:
        if not isinstance(payload,dict):
            raise ValueError("Formát dat")
        uloz(db, station, case, request, payload, schema)
    except (ValueError,TypeError,OverflowError):
        return [4,request,"PropertyConstraintViolation","Neplatné nebo rozporné oznámení.",{}]
    return [3,request,{}]


async def sluzba():
    from websockets.asyncio.server import unix_serve
    registry = json.loads(Path("/etc/polarita-ocpp-test/stanice.json").read_bytes(),object_pairs_hook=jednoznacne)
    if not registry or not all(re.fullmatch(r"[A-Z0-9-]{1,40}",key) and re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}",case) for key,case in registry.items()):
        raise ValueError("Neplatný registr stanic.")
    with ZipFile(ROOT/"ocpp-2.1.0-py3-none-any.whl") as wheel:
        schema = json.loads(wheel.read("ocpp/v21/schemas/StatusNotificationRequest.json"))
    priprav(DB)
    async def handle(ws):
        station = ws.request.path.removeprefix("/stanice/")
        if ws.request.path != "/stanice/"+station or station not in registry or ws.subprotocol != PROTOCOL:
            await ws.close(1008,"Neregistrovaná stanice nebo protokol.")
            return
        async for wire in ws:
            try:
                answer = await asyncio.to_thread(odpoved,wire,DB,station,registry[station],schema)
            except (ValueError,RecursionError):
                await ws.close(1002,"Neplatná zpráva OCPP.")
                return
            await ws.send(json.dumps(answer,ensure_ascii=False))
    async with unix_serve(handle, SOCKET, subprotocols=[PROTOCOL], max_size=16384, compression=None):
        await asyncio.Future()


if __name__ == "__main__":
    sys.path.insert(0,str(ROOT/"websockets-17.4-py3-none-any.whl"))
    asyncio.run(sluzba())
