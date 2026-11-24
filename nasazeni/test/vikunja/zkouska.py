"""Ověří přístup správce, práci s úkolem a zneplatnění obnovovací relace přes HTTPS."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
import re
import secrets
import sys
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
    raise ValueError("Neplatný název TEST")
realm = "https://" + host + "/identita/realms/polarita/"
origin = f"https://{host}:8447"
callback = origin + "/auth/openid/keycloak"


class Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not (newurl.startswith(realm) or newurl.split("?", 1)[0] == callback):
            raise RuntimeError("Návrat opustil klienta TEST")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Login(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "form" and fields.get("id") == "kc-form-login":
            self.action = fields.get("action")


web = build_opener(Redirect(), HTTPCookieProcessor(CookieJar()))


def api(method, path, payload=None, token=None):
    headers = {"Content-Type": "application/json", "Origin": origin}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(origin + "/api/v1/" + path, method=method, headers=headers,
                  data=None if payload is None else json.dumps(payload).encode())
    with web.open(req, timeout=45) as res:
        body = res.read()
    return json.loads(body) if body else None


def denied(method, path):
    try:
        api(method, path)
    except HTTPError as err:
        if err.code == 401:
            return
        raise
    raise RuntimeError("Ukončená nebo anonymní relace získala přístup")


denied("GET", "projects")
info = api("GET", "info")
auth = info["auth"]
provider, = auth["openid_connect"]["providers"]
if (auth["local"]["enabled"] or auth["local"]["registration_enabled"] or provider["key"] != "keycloak"
        or provider["auth_url"] != realm + "protocol/openid-connect/auth" or provider["client_id"] != "vikunja"):
    raise RuntimeError("Úkolovník používá jiného poskytovatele přihlášení")
state = secrets.token_urlsafe(24)
query = urlencode({"state": state, "scope": provider["scope"], "response_type": "code",
                   "client_id": "vikunja", "redirect_uri": callback})
with web.open(provider["auth_url"] + "?" + query, timeout=45) as res:
    login = Login()
    login.feed(res.read().decode())
    action = urljoin(res.url, login.action or "")
if not login.action or not action.startswith(realm + "login-actions/"):
    raise RuntimeError("Chybí formulář přihlášení správce")
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    raise ValueError("Chybí heslo TEST")
with web.open(Request(action, data=urlencode({"username": "spravce", "password": password}).encode()), timeout=60) as res:
    url = urlsplit(res.url)
    result = parse_qs(url.query)
if res.url.split("?", 1)[0] != callback or result.get("state") != [state] or len(result.get("code", [])) != 1:
    raise RuntimeError("Keycloak nepotvrdil návrat přihlášení")
token = api("POST", "auth/openid/keycloak/callback", {"code": result["code"][0], "redirect_url": callback}, None)["token"]
account = api("GET", "user", token=token)
if account["username"] != "spravce" or account["is_local_user"] or account["auth_provider"] != provider["name"]:
    raise RuntimeError("Úkolovník přihlásil jiného uživatele")
if "--nastenky" in sys.argv:
    # Stabilní identifikátory dovolují přejmenovat nástěnku v rozhraní.
    boards = {"ZAK": "Zakázkové", "MONT": "Montážní", "SLA": "SLA servisní"}
    existing = {}
    page = 1
    while True:
        rows = api("GET", f"projects?page={page}&per_page=50", token=token)
        if not rows:
            break
        existing.update({row["identifier"]: row for row in rows if row.get("identifier") in boards})
        page += 1
    for identifier, title in boards.items():
        board = existing.get(identifier)
        if board is None:
            board = api("PUT", "projects", {"title": title, "identifier": identifier}, token)
        path = f"projects/{board['id']}"
        persisted = api("GET", path, token=token)
        if persisted["identifier"] != identifier or persisted["owner"]["id"] != account["id"]:
            raise RuntimeError("Jiný vlastník nebo identifikátor nástěnky " + identifier)
        views = api("GET", path + "/views", token=token)
        kanban = next((view for view in views if view["view_kind"] == "kanban"), None)
        if kanban is None:
            kanban = api("PUT", path + "/views", {"title": "Kanban", "view_kind": "kanban",
                                                 "bucket_configuration_mode": "manual"}, token)
        viewpath = f"{path}/views/{kanban['id']}"
        restored = api("GET", viewpath, token=token)
        if restored["view_kind"] != "kanban" or restored["project_id"] != board["id"]:
            raise RuntimeError("Vikunja nepotvrdila nástěnku " + identifier)
        print(f"{title} ({identifier}): {origin}/{path}/{kanban['id']}", flush=True)
# Jen dočasný projekt založený tímto během.
project = api("PUT", "projects", {"title": "Kontrola instalace " + secrets.token_hex(6)}, token)["id"]
try:
    task = api("PUT", f"projects/{project}/tasks", {"title": "Ověřit předání úkolu"}, token)
    key = f"tasks/{task['id']}"
    api("POST", key, {"title": task["title"], "done": True}, token)
    saved = api("GET", key, token=token)
    if saved["project_id"] != project or saved["title"] != task["title"] or not saved["done"]:
        raise RuntimeError("Uložený úkol se neshoduje")
finally:
    api("DELETE", f"projects/{project}", token=token)
token = api("POST", "user/token/refresh")["token"]
api("POST", "user/logout", token=token)
denied("POST", "user/token/refresh")
print("Přes HTTPS se správce přihlásil přes Keycloak, založil projekt a úkol, dokončil jej a znovu ho přečetl. Po odhlášení byla obnova relace odmítnuta.")
