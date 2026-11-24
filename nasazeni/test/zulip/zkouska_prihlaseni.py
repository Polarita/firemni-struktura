"""Ověří nový webový přístup správce přes skutečný Keycloak a vlastní profil Zulipu."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
import re
import sys
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener


class Formular(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "form" and fields.get("id") == "kc-form-login":
            self.action = fields.get("action")


def main():
    host = sys.argv[1]
    if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
        raise ValueError("Neplatný název VPN")
    issuer = "https://" + host
    chat = issuer + ":8444"

    def allowed(url):
        parts = urlsplit(url)
        return parts.scheme == "https" and (
            parts.netloc == host + ":8444" or
            (parts.netloc == host and parts.path.startswith("/identita/"))
        )

    class Presmerovani(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not allowed(newurl):
                raise ValueError("Zulip přesměroval přihlášení mimo firemní aplikace")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    browser = build_opener(Presmerovani(), HTTPCookieProcessor(CookieJar()))
    login = chat + "/accounts/login/social/oidc/polarita"
    with browser.open(login, timeout=30) as response:
        form = Formular()
        form.feed(response.read().decode())
        if not form.action:
            raise RuntimeError("Přihlášení nezobrazilo formulář Keycloaku")
        action = urljoin(response.url, form.action)
        if urlsplit(action)[:2] != ("https", host) or not urlsplit(action).path.startswith("/identita/realms/polarita/login-actions/"):
            raise RuntimeError("Formulář nepatří testovacímu realmu")
        referer = response.url
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise ValueError("Chybí testovací heslo správce")
    fields = urlencode({"username": "spravce", "password": password}).encode()
    request = Request(action, data=fields, headers={"Origin": issuer, "Referer": referer})
    with browser.open(request, timeout=30) as response:
        if urlsplit(response.url)[:2] != urlsplit(chat)[:2]:
            raise RuntimeError("Přihlášení se nevrátilo do chatu")
    with browser.open(chat + "/json/users/me", timeout=15) as response:
        profile = json.load(response)
    if (profile.get("result") != "success" or profile.get("role") != 100 or
        profile.get("delivery_email", profile.get("email")) != "spravce@polarita.test" or profile.get("is_bot") is not False):
        raise RuntimeError("Profil Zulipu nepotvrdil přihlášeného vlastníka organizace")
    print("Nová relace Zulipu přes Keycloak potvrdila vlastní profil správce testovací organizace.")


if __name__ == "__main__":
    main()
