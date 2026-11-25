"""Protokol přihlášení. HTTPS adresa je argument, aktuální heslo vstupuje na stdin."""
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
for flag, port in (("--paperclip", 8445), ("--zulip", 8444)):
    if flag in sys.argv:
        expected = f'{origin}:{port}/'
        if f'href="{expected}"' not in overview:
            raise SystemExit("V přehledu správce chybí odkaz na " + expected)
        print("Přehled přihlášeného správce obsahuje odkaz na " + expected)
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
