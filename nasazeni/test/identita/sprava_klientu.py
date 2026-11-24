"""Připraví ve skutečném lokálním rozhraní Keycloaku účet pro správu klientů jediného TEST realmu."""
import fcntl
from html.parser import HTMLParser
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from urllib.parse import urlencode

ROOT = Path("/srv/polarita/data/bootstrap-test/keycloak-test/sprava")
REALM = "/admin/realms/polarita"
MANAGER = "polarita-sprava-klientu-test"
INITIAL = "polarita-zavedeni-test"


class ApiError(RuntimeError):
    def __init__(self, method, path, status):
        self.status = status
        super().__init__(f"Keycloak {method} {path.split('?')[0]} vrátil HTTP {status}")


def call(method, path, *, token=None, data=None, form=None, cookie=None):
    conn = HTTPConnection("127.0.0.1", 8080, timeout=90)
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if cookie:
        headers["Cookie"] = cookie
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        raw = urlencode(form).encode()
    else:
        raw = json.dumps(data).encode() if data is not None else None
        if raw is not None:
            headers["Content-Type"] = "application/json"
    try:
        conn.request(method, "/identita" + path, body=raw, headers=headers)
        res = conn.getresponse()
        body = res.read()
        if res.status >= 400:
            raise ApiError(method, path, res.status)
        return res.status, res.headers, body
    finally:
        conn.close()


def api(method, path, token, data=None):
    _, _, raw = call(method, path, token=token, data=data)
    return json.loads(raw) if raw else None


def secret(name):
    path = ROOT / (name + ".cred")
    if not path.exists():
        stage = path.with_suffix(".next")
        subprocess.run(["systemd-creds", "encrypt", "--with-key=tpm2", "--tpm2-pcrs=7",
                        "--name=" + name, "-", str(stage)], input=secrets.token_urlsafe(40).encode(), check=True)
        stage.chmod(0o600)
        stage.replace(path)
    return subprocess.check_output(["systemd-creds", "decrypt", "--name=" + name, str(path), "-"]).decode()


def login(realm, **fields):
    return json.loads(call("POST", "/realms/" + realm + "/protocol/openid-connect/token", form=fields)[2])["access_token"]


def manager_token(password):
    return login("polarita", grant_type="client_credentials", client_id=MANAGER, client_secret=password)


def verify_manager(token):
    if len(api("GET", REALM + "/clients?clientId=gitea", token)) != 1:
        raise RuntimeError("V testovacím realmu chybí klient Gitea")
    for path in (REALM + "/users?max=1", "/admin/realms/master/clients?max=1"):
        try:
            api("GET", path, token)
        except ApiError as e:
            if e.status != 403:
                raise
        else:
            raise RuntimeError("Strojová správa má neočekávaný přístup mimo klienty realmu")


class Welcome(HTMLParser):
    state = None

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "input" and attr.get("name") == "stateChecker":
            self.state = attr.get("value")


def first_user(password):
    _, headers, html = call("GET", "/")
    form = Welcome()
    form.feed(html.decode())
    cookies = SimpleCookie()
    for value in headers.get_all("Set-Cookie", []):
        cookies.load(value)
    csrf = cookies.get("WELCOME_STATE_CHECKER")
    if not csrf or not form.state or not secrets.compare_digest(csrf.value, form.state):
        raise RuntimeError("Místní úvodní stránka neumožnila vytvořit prvního správce")
    call("POST", "/", cookie=csrf.OutputString(attrs=[]), form={"username": INITIAL, "password": password,
         "passwordConfirmation": password, "email":"instalace@polarita.test", "firstName":"Instalace",
         "lastName":"TEST", "stateChecker":form.state})


def root_token(password):
    return login("master", grant_type="password", client_id="admin-cli", username=INITIAL, password=password)


def find_client(name, token):
    rows = api("GET", REALM + "/clients?" + urlencode({"clientId": name}), token)
    if len(rows) > 1:
        raise RuntimeError("Nejednoznačná identita klienta")
    return rows[0] if rows else None


def grant_manager(root, password):
    account = find_client(MANAGER, root)
    if not account:
        api("POST", REALM + "/clients", root, {"clientId":MANAGER, "protocol":"openid-connect", "enabled":True,
            "publicClient":False, "serviceAccountsEnabled":True, "standardFlowEnabled":False,
            "directAccessGrantsEnabled":False, "implicitFlowEnabled":False, "fullScopeAllowed":False, "secret":password})
        account = find_client(MANAGER, root)
    service = api("GET", REALM + "/clients/" + account["id"] + "/service-account-user", root)
    management = find_client("realm-management", root)["id"]
    role = api("GET", REALM + "/clients/" + management + "/roles/manage-clients", root)
    client_path = REALM + "/clients/" + account["id"]
    if account.get("fullScopeAllowed"):
        api("PUT", client_path, root, {"fullScopeAllowed":False})
    mapping = client_path + "/scope-mappings/clients/" + management
    if role["id"] not in [r["id"] for r in api("GET", mapping, root)]:
        api("POST", mapping, root, [role])
    if "kc-admin-api" not in account.get("defaultClientScopes", []):
        scope = next(x for x in api("GET", REALM + "/client-scopes", root) if x["name"] == "kc-admin-api")
        api("PUT", client_path + "/default-client-scopes/" + scope["id"], root)
    path = REALM + "/users/" + service["id"] + "/role-mappings/clients/" + management
    if role["id"] not in [r["id"] for r in api("GET", path, root)]:
        api("POST", path, root, [role])


def prepare():
    password = secret(MANAGER)
    pending = ROOT / (INITIAL + ".cred")
    try:
        verify_manager(manager_token(password))
    except ApiError as e:
        if e.status not in (400, 401, 403):
            raise
    else:
        if not pending.exists():
            return
    initial_password = secret(INITIAL)
    try:
        token = root_token(initial_password)
    except ApiError as e:
        if e.status not in (400, 401):
            raise
        if (ROOT / "sprava-predana").exists():
            verify_manager(manager_token(password))
            pending.unlink(missing_ok=True)
            return
        first_user(initial_password)
        token = root_token(initial_password)
    grant_manager(token, password)
    verify_manager(manager_token(password))
    rows = api("GET", "/admin/realms/master/users?" + urlencode({"username":INITIAL,"exact":"true"}), token)
    if len(rows) != 1 or rows[0]["username"] != INITIAL:
        raise RuntimeError("Nedohledán dočasný instalační účet")
    target = "/admin/realms/master/users/" + rows[0]["id"]
    (ROOT / "sprava-predana").touch(mode=0o600)
    api("PUT", target, token, {"enabled":False})
    try:
        root_token(initial_password)
    except ApiError as e:
        if e.status not in (400, 401):
            raise
    else:
        raise RuntimeError("Dočasný účet správce zůstal aktivní")
    pending.unlink()


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Příprava patří do testovací VM")
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if subprocess.check_output(["findmnt","-n","-o","SOURCE","-T",str(ROOT)],text=True).strip() != "polarita_zfs/data/bootstrap-test":
        raise RuntimeError("Chybí šifrované instalační úložiště")
    if "--lokalne" not in sys.argv:
        pid = json.loads(subprocess.check_output(["incus","query","/1.0/instances/keycloak-test/state"]))["pid"]
        os.execvp("nsenter", ["nsenter","--target",str(pid),"--net","--",sys.executable,__file__,"--lokalne"])
    with (ROOT / ".priprava").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prepare()
    print("Keycloak ověřil strojovou správu klientů realmu polarita. Přístup ke správě osob a realmu master zamítl.")


if __name__ == "__main__":
    main()
