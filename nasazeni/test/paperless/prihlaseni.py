"""Ověří anonymní přístup, přihlášení přes Keycloak a ukončení relace Paperless."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
    raise ValueError("Chybná adresa archivu")
origin = f"https://{host}:8448"
realm = f"https://{host}/identita/realms/polarita/"
start = origin + "/accounts/oidc/keycloak/login/"


class Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not (newurl.startswith(origin + "/") or newurl.startswith(realm)):
            raise RuntimeError("Návrat směřuje mimo testovací archiv")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.login = None
        self.csrf = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and a.get("id") == "kc-form-login":
            self.login = a.get("action")
        if tag == "input" and a.get("name") == "csrfmiddlewaretoken":
            self.csrf = a.get("value")


web = build_opener(Redirect(), HTTPCookieProcessor(CookieJar()))


def page(url, fields=None, referer=None):
    data = None if fields is None else urlencode(fields).encode()
    with web.open(Request(url, data=data, headers={"Referer": referer} if referer else {}), timeout=60) as res:
        form = Form()
        form.feed(res.read().decode())
        return res.url, form


def denied(req, codes):
    try:
        with web.open(req, timeout=30):
            pass
    except HTTPError as exc:
        if exc.code in codes:
            return
        raise
    raise RuntimeError("Rozhraní přijalo neočekávaný požadavek")


denied(origin + "/api/profile/", (401, 403))
denied(Request(origin + "/api/documents/post_document/", data=b""), (405,))
url, form = page(start)
if url == start and form.csrf:
    url, form = page(start, {"csrfmiddlewaretoken": form.csrf}, start)
action = urljoin(url, form.login or "")
if not form.login or not url.startswith(realm) or not action.startswith(realm + "login-actions/"):
    raise RuntimeError("Chybí přihlašovací formulář Keycloaku")
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    raise ValueError("Chybí testovací heslo")
url, _ = page(action, {"username": "spravce", "password": password}, url)
if not url.startswith(origin + "/"):
    raise RuntimeError("Keycloak nevrátil správce do archivu")
with web.open(origin + "/api/profile/", timeout=30) as res:
    account = json.load(res)
if account.get("email") != "spravce@polarita.test" or not any(a["provider"] == "keycloak" for a in account["social_accounts"]):
    raise RuntimeError("Archiv nepotvrdil účet správce z Keycloaku")
if len(sys.argv) > 2:
    case, doc_id, field_id = sys.argv[2:]
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case) or not doc_id.isdecimal() or not field_id.isdecimal():
        raise ValueError("Chybné označení dokumentu")
    for endpoint in ("/api/ui_settings/", "/api/saved_views/"):
        with web.open(origin + endpoint, timeout=45) as res:
            if res.status != 200 or res.headers.get_content_type() != "application/json":
                raise RuntimeError("Archiv nezpřístupnil nastavení dokumentového rozhraní správci.")
            json.load(res)
    with web.open(origin + "/api/documents/" + doc_id + "/", timeout=45) as res:
        doc = json.load(res)
    if (doc["id"] != int(doc_id) or doc["title"] != f"{case} – Předávací protokol TEST"
            or not any(f["field"] == int(field_id) and f["value"] == case for f in doc["custom_fields"])
            or "protokol" not in doc["content"].lower()):
        raise RuntimeError("Přihlášený správce neobdržel očekávaný protokol se spisem")
    print(f"Účet správce přečetl přes HTTPS dokument {doc_id} s výsledkem OCR a vazbou na spis {case}.")
logout = origin + "/accounts/logout/"
url, form = page(logout)
# Paperless v3 ukončuje přihlášení i při GET. Pokud vrátí potvrzovací
# formulář, odešleme jej. O výsledku rozhoduje nový požadavek na chráněný profil.
if url == logout and form.csrf:
    page(logout, {"csrfmiddlewaretoken": form.csrf}, logout)
denied(origin + "/api/profile/", (401, 403))
print("Paperless ověřil správce z Keycloaku, po odhlášení uzavřel profil a odmítl přímé nahrání mimo karanténu.")
