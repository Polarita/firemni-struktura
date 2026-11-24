"""Ověří vydání vzoru až po přihlášení ke skutečnému ředitelství."""
import hashlib
from http.cookiejar import CookieJar
import sys
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, build_opener

origin, expected = sys.argv[1:]
if urlsplit(origin).scheme != "https" or urlsplit(origin).path or len(expected) != 64:
    raise SystemExit("Ověření potřebuje původ HTTPS a kontrolní součet vzoru")
client = build_opener(HTTPCookieProcessor(CookieJar()))
path = origin + "/vzory/predavaci-protokol.pdf"
def require_login():
    with client.open(path, timeout=15) as res:
        if res.geturl() != origin + "/" or b'type="password"' not in res.read():
            raise RuntimeError("Vzor je dostupný bez přihlášení")
require_login()
secret = sys.stdin.readline().rstrip("\r\n")
with client.open(origin + "/prihlasit", urlencode({"username":"spravce","password":secret}).encode(), timeout=15) as res:
    if b'/vzory/predavaci-protokol.pdf' not in res.read():
        raise RuntimeError("Odkaz na protokol chybí")
with client.open(path, timeout=15) as res:
    if res.headers.get_content_type() != "application/pdf" or hashlib.file_digest(res,"sha256").hexdigest() != expected:
        raise RuntimeError("Stažená příloha se liší od ověřeného vzoru")
with client.open(origin + "/odhlasit", b"", timeout=15) as res:
    res.read()
require_login()
print("Přihlášený správce stáhl přes ředitelství shodný zapečetěný protokol. Po odhlášení odkaz znovu vyžaduje jméno a heslo.")
