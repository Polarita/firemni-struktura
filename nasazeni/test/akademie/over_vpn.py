"""Ověří přihlášení správce do Moodle a ukončení relace přes privátní HTTPS."""
import argparse
import re
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, build_opener

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("host")
parser.add_argument("--sso", action="store_true")
parser.add_argument("--kurz", action="store_true")
options = parser.parse_args()
host = options.host
if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
    sys.exit("Neplatný název VPN.")
origin = f"https://{host}:8451"
login = origin + "/login/index.php"
dashboard = origin + "/my/"
sso = options.sso


def same_origin(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc == f"{host}:8451"


def realm(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc == host and parts.path.startswith("/identita/realms/polarita/")


class Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not same_origin(newurl) and not (sso and realm(newurl)):
            raise RuntimeError("Přesměrování opustilo Akademii.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self.links = []
        self.text = []
        self.keycloak_form = None

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "form" and fields.get("id") == "kc-form-login":
            self.keycloak_form = fields.get("action")
        if tag == "input" and fields.get("name"):
            self.inputs[fields["name"]] = fields.get("value", "")
        if tag == "a" and fields.get("href"):
            self.links.append(fields["href"])


jar = CookieJar()
web = build_opener(Redirect(), HTTPCookieProcessor(jar))


def visit(url, data=None):
    if not same_origin(url) and not (sso and realm(url)):
        raise RuntimeError("Neočekávaný cíl přihlášení.")
    try:
        response = web.open(url, data=data, timeout=90)
    except HTTPError as error:
        raise RuntimeError(f"Přihlášení vrátilo HTTP {error.code} na {urlsplit(error.url).path}.") from None
    with response:
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
if sso:
    providers = [urljoin(login, href) for href in form.links
                 if same_origin(urljoin(login, href)) and urlsplit(urljoin(login, href)).path == "/auth/oauth2/login.php"]
    if len(providers) != 1:
        raise RuntimeError("Přihlašovací stránka Moodle neposkytla testovacího poskytovatele.")
    path, identity = visit(providers[0])
    action = identity.keycloak_form
    if not action or not realm(action) or not urlsplit(action).path.startswith("/identita/realms/polarita/login-actions/"):
        raise RuntimeError("Z přihlášení Moodle se neotevřel očekávaný formulář Keycloaku.")
    visit(action, urlencode({"username": "spravce", "password": password}).encode())
else:
    visit(login, urlencode({"username": "spravce", "password": password,
                            "logintoken": form.inputs["logintoken"]}).encode())
path, page = visit(dashboard)
if path != "/my/" or not any(c.name == "MoodleSessionPolAkademie" and c.secure for c in jar):
    raise RuntimeError("Přihlášený správce nemá přístup k nástěnce a zabezpečené relaci.")
profile_path, profile = visit(origin + "/user/editadvanced.php")
if profile_path != "/user/editadvanced.php" or profile.inputs.get("username") != "spravce":
    raise RuntimeError("Správa účtu nepotvrdila přihlášeného správce Akademie.")
if options.kurz:
    course_url = origin + "/course/view.php?idnumber=POL-TEST-AKADEMIE"
    course_path, course = visit(course_url)
    if course_path != "/course/view.php" or "Cvičná zkouška Akademie" not in " ".join(course.text):
        raise RuntimeError("Správce neotevřel cvičný kurz.")
    links = {urljoin(course_url, href) for href in course.links if same_origin(urljoin(course_url, href))}
    for module in ("page", "offlinequiz", "customcert"):
        if not any(urlsplit(url).path == f"/mod/{module}/view.php" for url in links):
            raise RuntimeError(f"V kurzu správce chybí odkaz na aktivitu {module}.")
    for url in sorted(links):
        if urlsplit(url).path == "/mod/page/view.php":
            path, content = visit(url)
            if path == "/mod/page/view.php" and "Zkontrolujte písmeno varianty" in " ".join(content.text):
                break
    else:
        raise RuntimeError("Z kurzu se nepodařilo otevřít návod k odpovědnímu listu.")
    print("Přihlášený správce otevřel kurz a návod k archu. V kurzu našel Offline Quiz i cvičné osvědčení.")
for href in page.links:
    logout = urljoin(dashboard, href)
    parts = urlsplit(logout)
    if same_origin(logout) and parts.path == "/login/logout.php" and parse_qs(parts.query).get("sesskey"):
        visit(logout)
        break
else:
    raise RuntimeError("Nástěnka neobsahuje odhlášení z ověřené relace.")
login_page()
method = "přes Keycloak" if sso else "místním účtem"
print(f"Správce se {method} přihlásil do Moodle a otevřel nástěnku i správu účtu. Po odhlášení Moodle opět zobrazil přihlašovací stránku.")
