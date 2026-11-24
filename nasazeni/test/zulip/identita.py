"""Nastaví přesnou návratovou adresu a klíč již založeného klienta Zulip."""
import hmac
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"identita"))
from sprava_klientu import MANAGER, REALM, api, find_client, manager_token, secret

if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
    raise SystemExit("Konfigurace klienta patří do firemní VM")
host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net",host):
    raise ValueError("Neočekávané jméno ředitelství")
if "--lokalne" not in sys.argv:
    pid = json.loads(subprocess.check_output(["incus","query","/1.0/instances/keycloak-test/state"]))["pid"]
    os.execvp("nsenter",["nsenter","--target",str(pid),"--net","--",sys.executable,__file__,host,"--lokalne"])
token = manager_token(secret(MANAGER))
client = find_client("zulip",token)
if not client or client["protocol"] != "openid-connect":
    raise RuntimeError("Chybí testovací klient týmového chatu")
path = REALM+"/clients/"+client["id"]
origin = "https://"+host+":8444"
key = subprocess.check_output(["incus","exec","-T","zulip-test","--","cat",
                               "/run/secrets/zulip__social_auth_oidc_secret"]).decode()
if not re.fullmatch("[A-Za-z0-9_-]{48,100}", key):
    raise RuntimeError("Neplatný klientský klíč")
desired = {"enabled":True,"publicClient":False,"standardFlowEnabled":True,"implicitFlowEnabled":False,
           "directAccessGrantsEnabled":False,"serviceAccountsEnabled":False,"clientAuthenticatorType":"client-secret",
           "redirectUris":[origin+"/complete/oidc/"],"webOrigins":[origin]}
if any(client.get(k)!=v for k,v in desired.items()) or not hmac.compare_digest(api("GET",path+"/client-secret",token)["value"],key):
    api("PUT",path,token,{**client,**desired,"secret":key})
current = find_client("zulip",token)
if any(current.get(k)!=v for k,v in desired.items()) or not hmac.compare_digest(api("GET",path+"/client-secret",token)["value"],key):
    raise RuntimeError("Keycloak nepotvrdil důvěrného klienta")
print("Keycloak potvrdil klienta Zulip a návratovou adresu přihlášení.")
