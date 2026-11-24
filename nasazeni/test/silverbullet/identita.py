"""Připojí webovou paměť k existujícímu správci TEST bez osobních klíčů."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "identita"))
from sprava_klientu import MANAGER, REALM, api, find_client, manager_token, secret

client_id = "oauth2-proxy-silverbullet"
if os.geteuid() or os.uname().nodename.split(".")[0] != "polarita-hq":
    raise SystemExit("Připojení patří do VM polarita-hq.")
if sys.argv[1:] != ["--lokalne"]:
    pid = json.loads(subprocess.check_output(["incus", "query", "/1.0/instances/keycloak-test/state"]))["pid"]
    os.execvp("nsenter", ["nsenter", "--target", str(pid), "--net", "--", sys.executable, __file__, "--lokalne"])
url = subprocess.check_output(["incus","exec","-T","gitea-test","--","cat","/etc/polarita-gitea/url"],text=True).strip()
u = urlsplit(url)
if u.scheme != "https" or u.path != "/git/" or not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", u.netloc):
    raise ValueError("Neočekávaný HTTPS vstup TEST")
origin = "https://" + u.netloc
callback = origin + ":8446/pamet/oauth2/callback"
token = manager_token(secret(MANAGER))
client = find_client(client_id, token)
if not client or client["protocol"] != "openid-connect":
    raise RuntimeError("Chybí testovací klient webové paměti")
path = REALM + "/clients/" + client["id"]
settings = {"enabled": True, "publicClient": False, "standardFlowEnabled": True,
            "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False, "clientAuthenticatorType": "client-secret",
            "redirectUris": [callback], "webOrigins": [origin + ":8446"]}
if any(client.get(k) != v for k, v in settings.items()):
    api("PUT", path, token, {**client, **settings})
updated = find_client(client_id, token)
if any(updated.get(k) != v for k, v in settings.items()):
    raise RuntimeError("Neshoda v konfiguraci klienta")
value = api("GET", path + "/client-secret", token)["value"]
if not value or "\n" in value:
    raise RuntimeError("Chybí klíč klienta")
inside = ["incus", "exec", "-T", "silverbullet-test", "--"]
# Soubor s tajemstvím převezme pouze systemd jako přihlašovací údaj služby.
subprocess.run(inside + ["sh","-ec", """umask 077
cd /etc/polarita-silverbullet
cat >client.next
mv -T client.next client
if [ ! -s cookie ]; then head -c 32 /dev/urandom >cookie.next && mv -T cookie.next cookie; fi
"""], input=value.encode(), check=True)
print(u.hostname)
