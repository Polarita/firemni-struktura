"""Spouští se jen uvnitř jednorázově obnovené instance bez sítě."""
import base64
import hashlib
import json
from pathlib import Path
import ssl
import sys
import time
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

if set(p.name for p in Path("/sys/class/net").iterdir()) != {"lo"}:
    raise SystemExit("Obnovená kopie musí mít pouze loopback")
http = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(
    cafile="/var/lib/polarita-openbao/tls/server.crt")))


def call(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    with http.open(Request("https://127.0.0.1:8200/v1/" + path, data=data,
                           headers=headers, method=method), timeout=10) as res:
        raw = res.read()
    return json.loads(raw) if raw else {}


payload = json.load(sys.stdin)
for _ in range(45):
    try:
        status = call("GET", "sys/seal-status")
        if status["initialized"] and not status["sealed"] and status["storage_type"] == "raft":
            break
    except OSError:
        pass
    time.sleep(1)
else:
    raise RuntimeError("Kopie se neodemkla")

attempt = call("PUT", "sys/generate-root/attempt", {})
if attempt["required"] != 3:
    raise RuntimeError("Nesouhlasí práh obnovy")
for i, share in enumerate(payload["shares"][:3], 1):
    result = call("PUT", "sys/generate-root/update", {"nonce": attempt["nonce"], "key": share})
    if result["complete"] != (i == 3):
        raise RuntimeError("Obnova nevyžadovala přesně tři podíly")
encoded = result["encoded_token"]
masked = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
otp = attempt["otp"].encode()
token = bytes(a ^ b for a, b in zip(masked, otp, strict=True)).decode()
value = call("GET", "test/data/reditelstvi", token=token)["data"]["data"]["vzorek"]
if hashlib.sha256(value.encode()).hexdigest() != payload["digest"]:
    raise RuntimeError("Hodnota z obnoveného Raftu nesouhlasí s původní")
call("POST", "auth/token/revoke-self", {}, token)
try:
    call("GET", "auth/token/lookup-self", token=token)
except HTTPError as error:
    if error.code != 403:
        raise
else:
    raise RuntimeError("Nový root token kopie zůstal platný")
print("Izolovaná kopie přečetla původní hodnotu. Obnova vyžadovala tři podíly a dočasný root token byl zrušen.")
