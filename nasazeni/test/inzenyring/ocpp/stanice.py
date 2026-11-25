"""Zkouška diagnostiky skutečnými rámci mezi místní stanicí a přijímačem TEST."""
import asyncio
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parent/"websockets-17.4-py3-none-any.whl"))
from websockets.asyncio.client import unix_connect
from websockets.exceptions import ConnectionClosed

SOCKET = "/run/polarita-ocpp-test/prijem.sock"


async def zkus():
    for name,status in (("EV-TEST-01","Available"),("EV-TEST-02","Faulted")):
        uri = "ws://localhost/stanice/"+name
        async with unix_connect(SOCKET,uri=uri,subprotocols=["ocpp2.1"],compression=None) as ws:
            if ws.subprotocol != "ocpp2.1":
                raise ValueError("Chybí sjednaný protokol.")
            async def send(action, req, payload):
                await ws.send(json.dumps([2,req,action,payload]))
                return json.loads(await asyncio.wait_for(ws.recv(),10))
            for minute,value in ((10,"Occupied"),(12,status)):
                stamp = f"2026-11-25T08:{minute}:00Z"
                req = str(uuid.uuid5(uuid.NAMESPACE_URL,"polarita.test/"+name+"/"+stamp))
                payload = {"connectorStatus":value,"timestamp":stamp,"evseId":1,"connectorId":1}
                for _ in range(2):
                    if await send("StatusNotification",req,payload) != [3,req,{}]:
                        raise ValueError("Příjem nepotvrdil totožnou zprávu.")
            if (await send("StatusNotification",req,{**payload,"evseId":2}))[:3] != [4,req,"PropertyConstraintViolation"]:
                raise ValueError("Příjem přijal kolidující opakování.")
            for command in ("Reset","UpdateFirmware"):
                if (await send(command,req,{}))[:3] != [4,req,"NotSupported"]:
                    raise ValueError("Čtecí kanál přijal řídicí příkaz.")
        print(name,value,"· sjednáno ocpp2.1, přijaty stavy, odmítnuta kolize a řídicí příkazy",flush=True)
    async with unix_connect(SOCKET,uri="ws://localhost/stanice/CIZI",subprotocols=["ocpp2.1"]) as ws:
        try:
            await ws.recv()
        except ConnectionClosed as err:
            if err.rcvd and err.rcvd.code == 1008:
                return
        raise ValueError("Příjem dovolil neregistrovanou stanici.")


if __name__ == "__main__":
    asyncio.run(zkus())
