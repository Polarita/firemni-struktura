"""Přes VPN předá vzor z ředitelství a znovu načte stejné potvrzení."""
from datetime import datetime, timedelta
from hashlib import sha256
from http.cookiejar import CookieJar
import json
import re
import sys
from urllib import error, parse, request
from uuid import NAMESPACE_URL, uuid5

class NeocekavanyStav(RuntimeError):
    def __init__(self, method, path, status, expected):
        self.status = status
        super().__init__(f"{method} {path} vrátil HTTP {status}, očekáván {expected}.")


def pripojeni(origin):
    if not re.fullmatch(r"https://[a-z0-9.-]+\.ts\.net", origin):
        raise ValueError("Chybí vstup ředitelství")
    browser = request.build_opener(request.HTTPCookieProcessor(CookieJar()))

    def call(method, path, content=None, mime=None, status=200, source=None):
        headers = {"Origin": origin if source is None else source}
        if mime:
            headers["Content-Type"] = mime
        req = request.Request(origin + path, data=content, headers=headers, method=method)
        try:
            res = browser.open(req, timeout=150)
        except error.HTTPError as exc:
            res = exc
        with res:
            if method == "GET" and path.startswith("/lhutnik-test/api/") and res.geturl() == origin + "/":
                raise NeocekavanyStav(method, path, 401, status)
            if res.status != status:
                raise NeocekavanyStav(method, path, res.status, status)
            return res.read()

    return call


def prihlasit(call, password):
    if not password:
        raise ValueError("Chybí testovací heslo")
    call("POST", "/prihlasit", parse.urlencode({"username":"spravce", "password":password}).encode(),
         "application/x-www-form-urlencoded")


def over(origin, password):
    api = "/lhutnik-test/api/"
    call = pripojeni(origin)
    no_login = api + "sanony/POL-2026-00001/00000000-0000-4000-8000-000000000001"
    call("PUT", no_login, b"%PDF-TEST", "application/pdf", 401)
    prihlasit(call, password)
    case = json.loads(call("POST", api+"spisy", json.dumps({
        "pozadavek":str(uuid5(NAMESPACE_URL, "polarita.test/web-spisy")), "branch_id":101}).encode(),
        "application/json"))["case_id"]
    pdf = call("GET", "/vzory/predavaci-protokol.pdf")
    if not pdf.startswith(b"%PDF-"):
        raise RuntimeError("Portál nevydal vzor testovacího protokolu")
    key = str(uuid5(NAMESPACE_URL, "polarita.test/prijem-48h/" + case + "/" + sha256(pdf).hexdigest()))
    route = api + "sanony/" + case + "/" + key
    call("PUT", route, pdf, "application/pdf", 403, source="https://jiny.invalid")
    call("PUT", route, b"TEST", "application/pdf", 415)
    one = json.loads(call("PUT", route, pdf, "application/pdf"))
    two = json.loads(call("PUT", route, pdf, "application/pdf"))
    if any(one[k] != two[k] for k in ("priloha","case_id","prijato","termin","bajtu")) or one["case_id"] != case or one["priloha"] != key or one["bajtu"] != len(pdf):
        raise RuntimeError("Opakování nepotvrdilo stejnou přílohu")
    if datetime.fromisoformat(one["termin"]) - datetime.fromisoformat(one["prijato"]) != timedelta(hours=48):
        raise RuntimeError("Potvrzení neobsahuje lhůtu 48 hodin")
    call("PUT", route, pdf + b"\n", "application/pdf", 409)
    rows = json.loads(call("GET", api+"sanony/"+case))
    if sum(r["priloha"] == key and r["termin"] == one["termin"] for r in rows) != 1:
        raise RuntimeError("Karta spisu neukázala právě jedno potvrzení")
    print(f"Ředitelství převzalo testovací PDF ke spisu {case}. Opakované odeslání vrátilo stejný termín 48 hodin.")
    print("Anonymní příjem, cizí původ, jiný formát a záměna obsahu pod stejným číslem byly odmítnuty.")

if __name__ == "__main__":
    over(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
