"""Ověří stejnou identitu přes běžné HTTP rozhraní e-shopu v TEST."""
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
import http.client
import json
import re
import ssl
import sys

host = sys.argv[1]
if host == "127.0.0.1":
    connect = lambda: http.client.HTTPConnection(host,9000,timeout=35)
elif re.fullmatch(r"[a-z0-9-]+(?:[.][a-z0-9-]+)+[.]ts[.]net",host):
    connect = lambda: http.client.HTTPSConnection(host,8450,timeout=45,context=ssl.create_default_context())
else:
    sys.exit("Neočekávaný název přihlašovacího serveru.")

def call(method, path, status, body=None, token=None, publishable=None):
    headers = {"Content-Type":"application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = "Bearer "+token
    if publishable:
        if token or not path.startswith("/store/"):
            raise ValueError("Publikovatelný klíč je určen pro zákaznické rozhraní.")
        headers["x-publishable-api-key"] = publishable
    conn = connect()
    try:
        conn.request(method,path,json.dumps(body).encode() if body is not None else None,headers)
        res=conn.getresponse()
        if res.status!=status:
            raise RuntimeError(f"Rozhraní {method} {path} vrátilo HTTP {res.status}, očekáváno {status}.")
        data=res.read(1<<20)
        return json.loads(data) if status==200 and "application/json" in res.getheader("Content-Type","") else data
    finally:
        conn.close()

email="spravce@polarita.test"
call("GET","/admin/users/me",401)
token=call("POST","/auth/user/emailpass",200,{"email":email,"password":sys.stdin.readline().rstrip("\r\n")})["token"]
if call("GET","/admin/users/me",200,token=token)["user"]["email"] != email:
    sys.exit("Nesouhlasí přihlášený účet.")
print("Správce se svým testovacím heslem otevřel vlastní účet Medusy. Anonymní profil byl odmítnut.")

if len(sys.argv) == 2:
    sys.exit(0)
if sys.argv[2:] == ["--objednavka"] and host == "127.0.0.1":
    from katalog import katalog
    from objednavka import objednej
    from pathlib import Path
    fixtures = katalog(call, token)
    objednej(call, token, fixtures)
    public = {key: fixtures[key] for key in ("publishable", "region_id", "product_id", "shipping_option_id")}
    if not public["publishable"].startswith("pk_"):
        sys.exit("Katalog neobsahuje veřejný klíč Store API.")
    destination = Path("/var/lib/polarita-medusa-test/katalog.json")
    temporary = destination.with_suffix(".next")
    temporary.write_text(json.dumps(public))
    temporary.replace(destination)
    sys.exit(0)
if sys.argv[2:] != ["--sklad"]:
    sys.exit("Neznámá volba zkoušky.")

# Pevná sada zkoušky dovolí pokračovat po přerušení bez zakládání dalšího zboží.
def key(name):
    return str(uuid5(NAMESPACE_URL, "urn:polarita:test:medusa:prejimka:v1:" + name))

api = "/admin/sklad/bubny"
label = "TEST-PREJIMKA-BUBEN-01"
case = "POL-2026-99001"

def movement(name, operation, length, status=200, **values):
    return call("POST", api, status, {"id": key(name), "operace": operation, "mm": length, **values}, token)

movement("buben", "prijem", 100000, stitek=label, varianta="test-kabel", sklad="MAIN-101")
movement("rezervace", "rezervace", 70000, buben=key("buben"), spis=case)
origin = {"rezervace": key("rezervace"), "stitek": label, "spis": case}
movement("cizi-stavba", "vydej", 1000, 404, **{**origin, "spis": "POL-2026-99002"})
movement("nadlimitni", "vydej", 70001, 409, **origin)
for _ in range(2):
    movement("vydej", "vydej", 45250, **origin)
movement("vydej", "vydej", 45251, 409, **origin)
movement("uvolneni", "uvolneni", 24750, **origin)
drum = call("GET", api + "?stitek=" + label, 200, token=token)["buben"]
if (drum["id"] != key("buben") or drum["rezervace"]
        or tuple(int(drum[k]) for k in ("prijato_mm","skladem_mm","rezervovano_mm","volno_mm"))
        != (100000, 54750, 0, 54750)):
    sys.exit("Po dokončení výdeje nesouhlasí zůstatky testovacího bubnu.")
print("Skladové API přijalo testovací buben, rezervovalo 70 m a vydalo 45,250 m. Po opakování výdeje zbývá 54,750 m.")

endpoint = "/admin/reklamace"
received = "2026-01-04T12:03:04.123456Z"
asserted = "2026-01-03T08:09:10.654321Z"
rma = {"id": key("reklamace"), "received_at": received, "complaint_asserted_at": asserted,
       "druh": "k_posouzeni", "objednavka": "TEST-PREJIMKA-01"}
call("POST", endpoint, 200, rma, token)
endpoint += "/" + rma["id"]
change = {"pozadavek": key("zarazeni"), "verze": 1, "druh": "b2c_reklamace"}
for _ in range(2):
    call("POST", endpoint, 200, change, token)
result = call("GET", endpoint, 200, token=token)["reklamace"]
if (result["id"] != rma["id"] or result["druh"] != "b2c_reklamace" or result["verze"] != 2
        or datetime.fromisoformat(result["received_at"]) != datetime.fromisoformat(received)
        or datetime.fromisoformat(result["complaint_asserted_at"]) != datetime.fromisoformat(asserted)):
    sys.exit("Nesouhlasí časy nebo historie reklamace ve správním API.")
print("Správce zařadil reklamaci. Dvojí odeslání zachovalo jedinou změnu a původní okamžiky uplatnění a příjmu.")
