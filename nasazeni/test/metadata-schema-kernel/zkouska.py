"""Skutečný unixový HTTP vstup, dvě relace, čtecí MCP a vratná DB migrace."""
import concurrent.futures
import http.client
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from uuid import UUID, NAMESPACE_URL, uuid5

from model import load, migrations
from mcp import PREFIX, VERSION


class Local(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(20)
        self.sock.connect("/run/polarita-metadata-test/api.sock")


def request(method, path, body=None, tag=None):
    headers = {"Content-Type": "application/json"}
    if tag:
        headers["If-Match"] = tag
    conn = Local("localhost", timeout=20)
    try:
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        res = conn.getresponse()
        raw = res.read()
        payload = json.loads(raw) if res.getheader("Content-Type").startswith("application/json") else raw.decode()
        return res.status, res.getheader("ETag"), payload
    finally:
        conn.close()


def sql(stmt, role="postgres", ok=True):
    cmd = ["runuser","-u","postgres","--","psql","-XqAtw","-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik"]
    res = subprocess.run(cmd, input=f'SET ROLE "{role}";\n'+stmt, text=True, capture_output=True)
    if (res.returncode == 0) != ok:
        raise RuntimeError("Neshoda při databázové zkoušce: " + res.stderr[:300])
    return res.stdout.strip()


def mcp(src, items):
    messages = []
    for idx, (method, args) in enumerate(items):
        meta = {PREFIX+"protocolVersion":VERSION, PREFIX+"clientCapabilities":{}}
        messages.append(json.dumps({"jsonrpc":"2.0","id":idx+1,"method":method,"params":{"_meta":meta, **args}}))
    run = subprocess.run(["runuser","-u","pol_metadata_read","--","python3",str(src/"mcp.py"),
                          str(src/"vystup/entity.json")], input="\n".join(messages)+"\n",text=True,capture_output=True,check=True)
    return [json.loads(line) for line in run.stdout.splitlines()]


def over_spisy(src):
    # Pevné klíče ponechají při opakované instalaci stejné zkušební spisy.
    keys = [str(uuid5(NAMESPACE_URL, "polarita.test/zkouska-spisu/" + str(n))) for n in range(3)]
    def pridat(key):
        status, _, row = request("POST", "/api/spisy", {"pozadavek":key, "branch_id":101})
        if status != 200:
            raise RuntimeError(f"Založení spisu přes místní API vrátilo HTTP {status}.")
        assert row["pozadavek"] == key
        return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(pridat, [keys[0], keys[0], *keys[1:]]))
    assert rows[0] == rows[1]
    assert len({row["case_id"] for row in rows}) == 3
    for row in rows:
        assert row["alias"] == row["case_id"].replace("POL-", "POL-101-", 1)
        for name in ("case_id", "alias"):
            status, _, result = request("GET", "/api/spisy/" + row[name])
            assert status == 200 and result == row
    assert request("GET", "/api/spisy/" + rows[0]["alias"].replace("POL-101-", "POL-109-"))[0] == 404
    assert request("POST", "/api/spisy", {"pozadavek":keys[0], "branch_id":100})[0] == 400
    identifiers = [rows[0]["case_id"], rows[0]["alias"], rows[0]["alias"].replace("POL-101-", "POL-109-"), 3]
    calls = mcp(src, [("tools/call", {"name": "spisy_najdi", "arguments": {"oznaceni": i}}) for i in identifiers])
    assert all(call["result"]["structuredContent"] == rows[0] for call in calls[:2])
    assert all(call["result"]["isError"] for call in calls[2:])
    sql("UPDATE polarita_test_spisy.spis SET branch_id=101 WHERE false;", "pol_metadata_read", ok=False)
    print("Čtecí MCP vrátil totožnou kartu přes číslo i pobočkový alias a odmítl neplatné označení.")
    sql("UPDATE polarita_test_spisy.rada SET posledni=0 WHERE false;", "pol_metadata_api", ok=False)
    print("Opakované a souběžné založení zachovalo jediné číslo spisu. Tři spisy mají původní číslo i alias pobočky 101.")


def check(src):
    for attempt in range(30):
        try:
            status, _, form = request("GET", "/")
            break
        except (FileNotFoundError, ConnectionRefusedError):
            if attempt == 29:
                raise
            time.sleep(1)
    assert status == 200 and all(f'name="{key}"' in form for key in ("popis","dny","vyrizeno"))
    status, _, api = request("GET", "/openapi.json")
    assert status == 200 and api["openapi"] == "3.2.1" and "put" in api["paths"]["/api/termin/{id}"]
    route = "/api/termin"
    label = "TEST-F22-" + secrets.token_hex(12)
    base = {"popis":label, "dny":2, "vyrizeno":False}
    assert request("POST", route, {**base, "dny":False})[0] == 400
    assert request("POST", route, {**base, "id":"x"})[0] == 400
    created, tag, row = request("POST", route, base)
    assert created == 201 and tag == '"1"' and row["version"] == 1, (created, tag, row)
    key = str(UUID(row["id"]))
    path = route + "/" + key
    try:
        assert request("GET", path) == (200, tag, row)
        assert request("PUT", path, base)[0] == 428
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(request, "PUT", path, {**base, "dny":n}, tag) for n in (4, 5)]
            outcomes = [job.result() for job in jobs]
        assert sorted(item[0] for item in outcomes) == [200,412], outcomes
        status, new_tag, value = request("GET",path)
        assert status == 200 and value["dny"] in (4,5) and new_tag == '"2"'
        calls = mcp(src, [("server/discover",{}),("tools/list",{}),("tools/call",{"name":"get_termin","arguments":{"id":key}}),
                          ("tools/call",{"name":"set_termin","arguments":{"id":key}})])
        assert VERSION in calls[0]["result"]["supportedVersions"]
        assert [t["name"] for t in calls[1]["result"]["tools"]] == ["get_termin", "spisy_najdi"]
        assert calls[2]["result"]["structuredContent"] == value and calls[3]["error"]["code"] == -32602
        sql("UPDATE polarita_test_metadata.meta_termin SET version=1 WHERE false;", "pol_metadata_read", ok=False)
        sql("CREATE TABLE polarita_test_metadata.nesmi_vzniknout (id int);", "pol_metadata_api", ok=False)
    finally:
        sql(f"DELETE FROM polarita_test_metadata.meta_termin WHERE id='{key}' AND popis='{label}';")
    assert request("GET",path)[0] == 404
    data = load(src/"vzor.json")
    data["entity"] = "proba_" + secrets.token_hex(7)
    up, down = migrations(data)
    sql(up, "pol_metadata_ddl")
    try:
        sql(up, "pol_metadata_ddl")
        sql(up.replace("varchar(160)", "varchar(90)").replace("polarita-metadata-v1:", "cizi:"), "pol_metadata_ddl", ok=False)
    finally:
        sql(down, "pol_metadata_ddl")
    sql(down, "pol_metadata_ddl")
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp)/"wrong.json"
        for database, schema in [("keycloak","public"), ("db_erp_lhutnik","public"), ("db_paperclip","public")]:
            file.write_text(json.dumps({**data, "database":database, "schema":schema}))
            try:
                load(file)
            except ValueError:
                continue
            raise AssertionError("Cizí schéma přijato")
    over_spisy(src)
    print("PostgreSQL ověřil opakovanou migraci, odmítnutí cizí revize a rollback. Cizí aplikační schémata byla odmítnuta.")
    print("HTTP poskytlo formulář a OpenAPI. Dvě změny stejné verze vrátily 200 a 412, chybějící If-Match vrátil 428.")
    print("MCP skutečného čtecího účtu získal totožný záznam. Pokus o zápis databáze odmítla.")


if __name__ == "__main__":
    check(Path(sys.argv[1]))
