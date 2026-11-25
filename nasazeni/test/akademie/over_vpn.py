"""Ověří přihlášení správce do Moodle a ukončení relace přes privátní HTTPS."""
import re
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, build_opener

host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
    sys.exit("Neplatný název VPN.")
origin = f"https://{host}:8451"
login = origin + "/login/index.php"
dashboard = origin + "/my/"


def same_origin(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc == f"{host}:8451"


class Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not same_origin(newurl):
            raise RuntimeError("Přesměrování opustilo Akademii.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "input" and fields.get("name"):
            self.inputs[fields["name"]] = fields.get("value", "")
        if tag == "a" and fields.get("href"):
            self.links.append(fields["href"])


jar = CookieJar()
web = build_opener(Redirect(), HTTPCookieProcessor(jar))


def visit(url, data=None):
    with web.open(url, data=data, timeout=90) as response:
        page = Page()
        page.feed(response.read().decode("utf-8"))
        return urlsplit(response.url).path, page


def login_page():
    path, page = visit(dashboard)
    if path != "/login/index.php" or not page.inputs.get("logintoken"):
        raise RuntimeError("Anonymní návštěva nástěnky nevedla na přihlášení.")
    return page


form = login_page()
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    sys.exit("Chybí testovací heslo.")
visit(login, urlencode({"username": "spravce", "password": password,
                        "logintoken": form.inputs["logintoken"]}).encode())
path, page = visit(dashboard)
if path != "/my/" or not any(c.name == "MoodleSessionPolAkademie" and c.secure for c in jar):
    raise RuntimeError("Přihlášený správce nemá přístup k nástěnce a zabezpečené relaci.")
profile_path, profile = visit(origin + "/user/editadvanced.php")
if profile_path != "/user/editadvanced.php" or profile.inputs.get("username") != "spravce":
    raise RuntimeError("Správa účtu nepotvrdila přihlášeného správce Akademie.")
for href in page.links:
    logout = urljoin(dashboard, href)
    parts = urlsplit(logout)
    if same_origin(logout) and parts.path == "/login/logout.php" and parse_qs(parts.query).get("sesskey"):
        visit(logout)
        break
else:
    raise RuntimeError("Nástěnka neobsahuje odhlášení z ověřené relace.")
login_page()
print("Správce se přes VPN přihlásil do Moodle, otevřel nástěnku a správu účtu. Po odhlášení nástěnka opět vyžádala heslo.")
