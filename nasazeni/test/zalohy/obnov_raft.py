"""Otevře zachycený snapshot v novém Raftu uvnitř jednorázového kontejneru bez sítě."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import time
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

if not re.fullmatch(r"restic-obnova-[a-f0-9]{12}", socket.gethostname().split(".")[0]):
    raise SystemExit("Neplatný cíl obnovy Raftu")
if {item.name for item in Path("/sys/class/net").iterdir()} != {"lo"}:
    raise SystemExit("Pro obnovu Raftu je nutný pouze loopback")
if subprocess.check_output(["findmnt", "-no", "FSTYPE", "/run"]).strip() != b"tmpfs":
    raise SystemExit("Obnova potřebuje tmpfs")
os.umask(0o077)
root = Path("/var/tmp/obnova-polarita")
work = Path("/run/restic-raft")
work.mkdir()
(work/"data").mkdir()
Path("/var/lib/polarita-openbao/audit").mkdir(parents=True, exist_ok=True)
payload = json.load(sys.stdin)
(work/"seal").write_bytes(base64.b64decode(payload["seal"], validate=True))
address = "10.239.33.1"
subprocess.run(["ip","address","add",address+"/32","dev","lo"], check=True)
subprocess.run(["openssl","req","-x509","-newkey","ec","-pkeyopt","ec_paramgen_curve:prime256v1","-nodes",
                "-days","1","-subj","/CN=restic-raft","-addext","subjectAltName=IP:"+address,
                "-keyout",str(work/"tls.key"),"-out",str(work/"tls.crt")],stderr=subprocess.DEVNULL,check=True)
port = address+":18200"
(work/"server.hcl").write_text(f'''
disable_mlock = true
api_addr = "https://{port}"
cluster_addr = "https://{address}:18201"
storage "raft" {{
 path = "{work}/data"
 node_id = "polarita-hq-test"
}}
listener "tcp" {{
 address = "{port}"
 cluster_address = "{address}:18201"
 tls_cert_file = "{work}/tls.crt"
 tls_key_file = "{work}/tls.key"
}}
seal "static" {{
 current_key_id = "polarita-test-01"
 current_key = "file://{work}/seal"
}}
''')
client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=str(work/"tls.crt"))))


def request(method, path, body=None, token=None):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    headers = {"Content-Type": "application/json" if isinstance(body, dict) else "application/octet-stream"}
    if token:
        headers["X-Vault-Token"] = token
    req = Request("https://"+port+"/v1/"+path, data=data, headers=headers, method=method)
    with client.open(req, timeout=30) as response:
        content = response.read()
    return json.loads(content) if content else {}


def wait_for(probe):
    for _ in range(45):
        try:
            value = probe()
            if value:
                return value
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("Obnovovaný Raft ve stanoveném čase nepotvrdil očekávaný stav")


with (work/"server.log").open("wb") as log:
    server = subprocess.Popen(["/var/tmp/bao","server","-config="+str(work/"server.hcl")],
                              stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    try:
        wait_for(lambda: request("GET","sys/seal-status"))
        init = request("PUT","sys/init",{"recovery_shares":1,"recovery_threshold":1,"secret_shares":1,"secret_threshold":1,"stored_shares":1})
        wait_for(lambda: not request("GET","sys/seal-status")["sealed"])
        with (root/"openbao.snap").open("rb") as snapshot:
            request("POST","sys/storage/raft/snapshot",snapshot,init["root_token"])
        manager = wait_for(lambda: request("POST","auth/approle/login",payload["manager"])["auth"]["client_token"])
        role = "auth/approle/role/reditelstvi-test/"
        try:
            identity = request("GET",role+"role-id",token=manager)["data"]["role_id"]
            secret = request("POST",role+"secret-id",{},manager)["data"]["secret_id"]
            token = request("POST","auth/approle/login",{"role_id":identity,"secret_id":secret})["auth"]["client_token"]
            try:
                value = request("GET","test/data/reditelstvi",token=token)["data"]["data"]["vzorek"]
                if hashlib.sha256(value.encode()).hexdigest() != (root/"openbao.sha256").read_text().strip():
                    raise RuntimeError("Hodnota v obnoveném trezoru se liší od okamžiku zálohy")
            finally:
                request("POST","auth/token/revoke-self",{},token)
        finally:
            request("POST","auth/token/revoke-self",{},manager)
    finally:
        server.terminate()
        server.wait(timeout=20)
        (work/"seal").unlink(missing_ok=True)
print("OpenBao obnovil snapshot Raftu a přihlášená role přečetla původní hodnotu.")
