"""Ověří vstup přes skutečný prohlížečový protokol, relaci, organizaci a jednotlivé pozice."""
from http.cookiejar import CookieJar
import json
import re
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener


class BezPresmerovani(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Rozhraní Paperclipu přesměrovalo ověřovací požadavek")


def main():
    host = sys.argv[1]
    if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
        raise ValueError("Neplatná adresa firemní VPN")
    origin = "https://" + host + ":8445"
    browser = build_opener(BezPresmerovani(), HTTPCookieProcessor(CookieJar()))

    def visit(path, data=None):
        req = Request(origin + path, headers={"Origin": origin, "Content-Type": "application/json"},
                      data=json.dumps(data).encode() if data is not None else None)
        with browser.open(req, timeout=30) as response:
            if path == "/":
                return response.headers.get_content_type(), response.read()
            return json.load(response)

    def check_signed_out():
        try:
            session = visit("/api/auth/get-session")
        except HTTPError as exc:
            if exc.code != 401:
                raise
            exc.close()
        else:
            if session is not None:
                raise RuntimeError("Prohlížeč bez přihlášení má neočekávanou relaci")

    mime, web = visit("/")
    if mime != "text/html" or b'id="root"' not in web:
        raise RuntimeError("Chybí nativní webové rozhraní Paperclipu")
    health = visit("/api/health")
    if health.get("status") != "ok" or health.get("deploymentMode") != "authenticated":
        raise RuntimeError("Paperclip nepotvrdil připravenost chráněné aplikace")
    check_signed_out()
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise ValueError("Chybí testovací heslo")
    email = "spravce@polarita.test"
    visit("/api/auth/sign-in/email", {"email": email, "password": password})
    if visit("/api/auth/get-session")["user"]["email"] != email:
        raise RuntimeError("Nesouhlasí profil přihlášeného správce")
    company, = [c for c in visit("/api/companies") if c["name"] == "Polarita s.r.o." and c["budgetMonthlyCents"] == 47000]
    rows = visit("/api/companies/" + company["id"] + "/agents")
    ids = {(a.get("metadata") or {}).get("polaritaId") for a in rows}
    if len(rows) != 20 or len(ids) != 20 or None in ids or sum(a["budgetMonthlyCents"] for a in rows) != 39950:
        raise RuntimeError("Rozhraní správce nepotvrdilo 20 pozic a provozní kvóty")
    if "--decisions" in sys.argv:
        approvals = visit("/api/companies/" + company["id"] + "/approvals")
        states = {}
        for item in approvals:
            sample = (item.get("payload") or {}).get("polarita") or {}
            number = sample.get("spis")
            if number not in ("TEST-POL-0000-00011", "TEST-POL-0000-00012", "TEST-POL-0000-00013"):
                continue
            if number in states or item["type"] != "request_board_approval":
                raise RuntimeError("Nejednoznačná položka nativní fronty TEST")
            detail = visit("/api/approvals/" + item["id"])
            if (detail["payload"] != item["payload"] or sample.get("test") is not True
                    or sample.get("pred") != {"stav":"rozpracován", "verze":1}
                    or sample.get("po") != {"stav":"ke kontrole", "verze":2}):
                raise RuntimeError("Přihlášený správce nevidí celý diff")
            states[number] = detail["status"]
        if (len(states) != 3 or states["TEST-POL-0000-00011"] != "approved" or
                states["TEST-POL-0000-00012"] != "rejected"):
            raise RuntimeError("Přes VPN nebyly dostupné všechny tři vzory Decisions")
        print("V nativní frontě správce otevřel tři vzory, jejich diff a oba výsledky hlasování.")
    visit("/api/auth/sign-out", {})
    check_signed_out()
    print("Přes VPN se správce přihlásil do Paperclipu, otevřel organizaci s 20 pozicemi a úspěšně se odhlásil.")


if __name__ == "__main__":
    main()
