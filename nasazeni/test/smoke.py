"""Protokol přihlášení. HTTPS adresa je argument, aktuální heslo vstupuje na stdin."""
import hashlib
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

origin = sys.argv[1].rstrip("/")
if urllib.parse.urlparse(origin).scheme != "https":
    raise SystemExit("Test přihlášení vyžaduje HTTPS")
secret = sys.stdin.readline().rstrip("\n")
if not secret:
    raise SystemExit("Chybí heslo")
jar = http.cookiejar.CookieJar()
browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request_page(path, data, status, final_path, needle):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(origin + path, data=body, headers={"Origin": origin})
    try:
        response = browser.open(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        if "1.1 polarita-caddy" not in (response.headers.get_all("Via") or []):
            raise SystemExit("Odpověď neprošla přes Caddy v zóně dmz_edge")
        # Prohlížeč při politice no-referrer může u POST odeslat Origin: null.
        if response.headers.get("Referrer-Policy") != "same-origin":
            raise SystemExit("Prohlížeč potřebuje původ pro odeslání přihlašovacího formuláře")
        page = response.read().decode()
        if (response.code != status or response.url != origin + final_path
                or needle not in page):
            raise SystemExit(f"Chyba testu {path}, HTTP {response.code}")
    print(f"OK {path} → {final_path} (HTTP {status})")
    return page


def check(path, data, status, final_path, needle):
    try:
        return request_page(path, data, status, final_path, needle)
    except (TimeoutError, urllib.error.URLError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if not isinstance(reason, TimeoutError):
            raise
        print(f"Ředitelství neodpovědělo včas při kontrole {path}.", file=sys.stderr)
        raise SystemExit(74) from None


check("/prehled", None, 200, "/", "Přihlášení do testovacího prostředí")
if "--dohled" in sys.argv:
    check("/dohled", None, 200, "/", "Přihlášení do testovacího prostředí")
check("/konfigurator", None, 200, "/", "Přihlášení do testovacího prostředí")
check("/prihlasit", {"username": "spravce", "password": "neplatne"}, 401, "/prihlasit", "nesouhlasí")
check("/prihlasit", {"username": "spravce", "password": secret}, 200, "/prehled", "Jste přihlášeni")
overview = check("/prehled", None, 200, "/prehled", "Jste přihlášeni")
for flag, suffix in (("--paperclip", ":8445/"), ("--zulip", ":8444/"), ("--akademie", ":8451/my/")):
    if flag in sys.argv:
        expected = origin + suffix
        if f'href="{expected}"' not in overview:
            raise SystemExit("V přehledu správce chybí odkaz na " + expected)
        print("Přehled přihlášeného správce obsahuje odkaz na " + expected)
if "--protokol-komise" in sys.argv:
    document = re.search(r'href="(/akademie-test/doklady/([0-9a-f]{64})\.pdf)">Stáhnout protokol', overview)
    if document is None:
        raise SystemExit("V přehledu chybí komisní protokol Akademie.")
    with browser.open(origin + document[1], timeout=60) as response:
        if (response.url != origin + document[1] or response.headers.get_content_type() != "application/pdf"
                or hashlib.file_digest(response, "sha256").hexdigest() != document[2]):
            raise SystemExit("Stažený komisní protokol má jiný obsah.")
    print("Správce stáhl přímo z přehledu zapečetěný komisní protokol s odpovídajícím SHA-256.")
if "--termin-akademie" in sys.argv:
    check("/lhutnik-test/", None, 200, "/lhutnik-test/", 'href="./zkousky"')
    deadlines = check("/lhutnik-test/zkousky", None, 200, "/lhutnik-test/zkousky", "Termíny zkoušek Akademie")
    if not re.search(r'<li>POL-[0-9]+ · <time datetime="20[0-9]{2}-[0-9]{2}-[0-9]{2}">', deadlines):
        raise SystemExit("Termín potvrzené zkoušky se v Lhůtníku nezobrazil.")
if "--decisions" in sys.argv:
    match = re.search(re.escape('href="' + origin + ':8445/') + r'[A-Z][A-Z0-9]{0,15}/approvals/' +
                      r'([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})">Vyzkoušet rozhodnutí ve vzorovém spisu</a>', overview)
    if not match:
        raise SystemExit("V přehledu správce chybí odkaz na vzorové rozhodnutí v Paperclipu")
    print("Přihlášený správce má v přehledu přímý odkaz na vzorový spis Decisions.")
check("/konfigurator", None, 200, "/konfigurator", "Konfigurátor paušálu")
if "--dohled" in sys.argv:
    check("/dohled", None, 200, "/dohled", "Checkmk · polarita-hq")
check("/odhlasit", {}, 200, "/", "Přihlášení do testovacího prostředí")
check("/prehled", None, 200, "/", "Přihlášení do testovacího prostředí")
if "--protokol-komise" in sys.argv:
    check(document[1], None, 200, "/", "Přihlášení do testovacího prostředí")

if "--termin-akademie" in sys.argv:
    check("/lhutnik-test/zkousky", None, 200, "/", "Přihlášení do testovacího prostředí")
