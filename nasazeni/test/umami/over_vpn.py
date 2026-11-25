"""Ověří stejný účet na soukromém HTTPS vstupu do Umami."""
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import json
import re
import sys


class BezPresmerovani(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
    raise ValueError("Neplatné jméno vstupu TEST.")
origin = f"https://{host}:8449"
web = build_opener(ProxyHandler({}), BezPresmerovani())


def call(path, *, data=None, token=None):
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = "Bearer "+token
    with web.open(Request(origin+path, data=json.dumps(data).encode() if data else None, headers=headers), timeout=60) as response:
        return json.load(response)


try:
    call("/api/me")
except HTTPError as e:
    if e.code != 401:
        raise
else:
    raise RuntimeError("Profil v analytice byl dostupný anonymně.")
with web.open(origin + "/login", timeout=60) as res:
    if res.headers.get_content_type() != "text/html" or b"umami" not in res.read().lower():
        raise RuntimeError("Chybí přihlašovací obrazovka Umami.")
login = call("/api/auth/login", data={"username": "spravce", "password": sys.stdin.readline().rstrip("\r\n")})
me = call("/api/me", token=login["token"])["user"]
if me["username"] != "spravce" or not me["isAdmin"]:
    raise RuntimeError("Profil neodpovídá správci TEST.")
sites = call("/api/websites/bd6c414c-cb6d-43e1-a9b7-6487272a450d", token=login["token"])
if sites["domain"] != "polarita.test":
    raise RuntimeError("Analytika nevrátila měřený testovací web.")
print("Anonymní profil byl odmítnut. Správce se přihlásil přes HTTPS a otevřel svůj měřený web v Umami.")
