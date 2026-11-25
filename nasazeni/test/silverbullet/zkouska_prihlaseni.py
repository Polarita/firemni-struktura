"""Ověří přihlášení, čtení a odhlášení webové paměti z nové HTTPS relace."""
import argparse
import hashlib
import json
from pathlib import Path
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("host")
parser.add_argument("--predavky", type=Path)
args = parser.parse_args()
host = args.host
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
if args.predavky:
    predavky = [json.loads(line) for line in args.predavky.read_text().splitlines()]
    if not predavky:
        raise ValueError("Chybí doklad k ověření webovou relací.")
    for doklad in predavky:
        path, digest = doklad["cesta"], doklad["sha256"]
        if not (re.fullmatch(r"08-Deniky-a-Predavky/log-instalace-[a-z0-9-]+\.md", path)
                and re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("Neplatná cesta nebo otisk předávky.")
        url = start + ".fs/" + path
        with web.open(url, timeout=30) as response:
            text = response.read(65537)
            _, marker, source = text.partition(b"```text\n")
            if (response.url != url or len(text) > 65536 or not marker or not source.endswith(b"\n```\n")
                    or hashlib.sha256(source[:-5]).hexdigest() != digest):
                raise RuntimeError("Webová paměť neposkytla přesný zdrojový protokol.")
    print(f"Správce v přihlášené webové paměti přečetl a ověřil {len(predavky)} předávací protokoly.")
with web.open(start, timeout=20) as response:
    if b"silverbullet" not in response.read().lower():
        raise RuntimeError("Chybí HTML aplikace SilverBullet")
# Po odhlášení z aplikace musí chráněná kontrola relace vrátit 401 i při trvajícím SSO.
class BezPresmerovani(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

logout = build_opener(BezPresmerovani(), HTTPCookieProcessor(jar))
try:
    with logout.open(start+"oauth2/sign_out", timeout=15) as response:
        response.read()
except HTTPError as err:
    if err.code not in (302, 303):
        raise
try:
    web.open(start+"oauth2/auth", timeout=10)
except HTTPError as err:
    if err.code != 401:
        raise
else:
    raise RuntimeError("Odhlášení zachovalo relaci paměti")
print("Anonymní čtení vyžádalo Keycloak. Správce otevřel SilverBullet a přečetl registr CZ-101. Po odhlášení již relace neplatila.")
