"""Kontroluje vydavatele v OIDC discovery, veřejný klíč realmu a uzavřenou administraci."""
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

base = sys.argv[1].rstrip("/")
issuer = base + "/realms/polarita"
if not base.startswith("https://") or not base.endswith("/identita"):
    raise SystemExit("Ověření vyžaduje HTTPS adresu identity")

for i in range(90):
    try:
        with urlopen(issuer + "/.well-known/openid-configuration", timeout=6) as res:
            discovery = json.load(res)
        break
    except (HTTPError, URLError, TimeoutError):
        if i == 89:
            raise
        time.sleep(3)
for field, path in {"issuer": "", "authorization_endpoint": "/protocol/openid-connect/auth",
                    "token_endpoint": "/protocol/openid-connect/token", "jwks_uri": "/protocol/openid-connect/certs",
                    "end_session_endpoint": "/protocol/openid-connect/logout"}.items():
    if discovery.get(field) != issuer + path:
        raise RuntimeError("Nesouhlasí OIDC adresa " + field)
with urlopen(discovery["jwks_uri"], timeout=8) as res:
    if not any(k["use"] == "sig" and k["kty"] == "RSA" for k in json.load(res)["keys"]):
        raise RuntimeError("Chybí podpisový klíč realmu")
for path in ("/admin/", "/realms/master/.well-known/openid-configuration"):
    try:
        with urlopen(base + path, timeout=8):
            raise RuntimeError("Správa je přístupná na aplikačním vstupu")
    except HTTPError as err:
        if err.code != 404:
            raise
print("Soukromý HTTPS vstup poskytuje discovery, podepisovací klíče a odhlášení realmu polarita. Správa vrací 404.")
