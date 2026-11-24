"""Ověří přihlášení, čtení a odhlášení webové paměti z nové HTTPS relace."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
import sys
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
    raise ValueError("Neplatný název VPN")
origin = "https://" + host + ":8446"
start = origin + "/pamet/"
register = start + ".fs/00-Meta/pobocky.md"


def allowed(url):
    u = urlsplit(url)
    return u.scheme == "https" and (
        (u.netloc == host + ":8446" and u.path.startswith("/pamet/"))
        or (u.netloc == host and u.path.startswith("/identita/"))
    )


class Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise RuntimeError("Požadavek opustil TEST paměť nebo Keycloak")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Login(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "form" and fields.get("id") == "kc-form-login":
            self.action = fields.get("action")


jar = CookieJar()
web = build_opener(Redirect(), HTTPCookieProcessor(jar))
with web.open(register, timeout=20) as res:
    login = Login()
    login.feed(res.read().decode())
    action = urljoin(res.url, login.action or "")
if not login.action or not allowed(action) or urlsplit(action).netloc != host:
    raise RuntimeError("Anonymní přístup nevedl na formulář Keycloaku")
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    raise RuntimeError("Chybí testovací heslo")
request = Request(action, data=urlencode({"username":"spravce", "password":password}).encode())
with web.open(request, timeout=25) as response:
    if response.url != register or b"CZ-101" not in response.read():
        raise RuntimeError("Návrat z Keycloaku neposkytl stránku registru")
with web.open(start, timeout=20) as response:
    if b"silverbullet" not in response.read().lower():
        raise RuntimeError("Chybí HTML aplikace SilverBullet")
# Po odhlášení z aplikace musí chráněná kontrola relace vrátit 401 i při trvajícím SSO.
from urllib.error import HTTPError
with web.open(start+"oauth2/sign_out?rd="+start+"oauth2/sign_in",timeout=20) as response:
    response.read()
try:
    web.open(start+"oauth2/auth", timeout=10)
except HTTPError as err:
    if err.code != 401:
        raise
else:
    raise RuntimeError("Odhlášení zachovalo relaci paměti")
print("Anonymní čtení vyžádalo Keycloak. Správce otevřel SilverBullet a přečetl registr CZ-101. Po odhlášení již relace neplatila.")
