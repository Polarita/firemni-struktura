"""Protokol přihlášení. HTTPS adresa je argument, aktuální heslo vstupuje na stdin."""
import http.cookiejar
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


def check(path, data, status, final_path, needle):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(origin + path, data=body, headers={"Origin": origin})
    try:
        response = browser.open(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        if (response.code != status or response.url != origin + final_path
                or needle not in response.read().decode()):
            raise SystemExit(f"Chyba testu {path}, HTTP {response.code}")
    print(f"OK {path} → {final_path} (HTTP {status})")


check("/prehled", None, 200, "/", "Přihlášení do testovacího prostředí")
check("/prihlasit", {"username": "spravce", "password": "neplatne"}, 401, "/prihlasit", "nesouhlasí")
check("/prihlasit", {"username": "spravce", "password": secret}, 200, "/prehled", "Jste přihlášeni")
check("/prehled", None, 200, "/prehled", "Jste přihlášeni")
check("/odhlasit", {}, 200, "/", "Přihlášení do testovacího prostředí")
check("/prehled", None, 200, "/", "Přihlášení do testovacího prostředí")
