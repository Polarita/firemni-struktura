"""Skutečný OIDC Authorization Code + PKCE klient nad testovacím účtem. Tajemství přijímá ze stdin."""
import base64
import hashlib
import json
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import secrets
import sys
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request


class Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and a.get("id") == "kc-form-login":
            self.action = a["action"]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


base = sys.argv[1].rstrip("/")
parts = urlsplit(base)
if parts.scheme != "https" or parts.path != "/identita" or not parts.hostname:
    raise SystemExit("Chybná adresa identity")
realm = base + "/realms/polarita"
endpoint = realm + "/protocol/openid-connect"
callback = realm + "/account/"
client = "account-console"
browser = build_opener(HTTPCookieProcessor(CookieJar()), NoRedirect())


def call(url, form=None, token=None):
    if (urlsplit(url).scheme, urlsplit(url).netloc) != (parts.scheme, parts.netloc):
        raise RuntimeError("Odlišný původ požadavku")
    req = Request(url, data=urlencode(form).encode() if form is not None else None)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with browser.open(req, timeout=15) as res:
            return res.status, res.headers, res.read()
    except HTTPError as err:
        with err:
            return err.code, err.headers, err.read()


def pkce():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, {"client_id": client, "redirect_uri": callback, "scope": "openid profile email",
                      "response_type": "code", "state": secrets.token_urlsafe(20),
                      "code_challenge": challenge, "code_challenge_method": "S256"}


verifier, authorize = pkce()
status, _, raw = call(endpoint + "/auth?" + urlencode(authorize))
form = Form()
form.feed(raw.decode())
if status != 200 or not form.action:
    raise RuntimeError("Chybí formulář centrálního přihlášení")
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    raise RuntimeError("Chybí testovací heslo")
code, headers, _ = call(urljoin(realm, form.action), {"username": "spravce", "password": password})
location = urlsplit(headers.get("Location", ""))
params = parse_qs(location.query)
if code != 302 or location._replace(query="", fragment="").geturl() != callback or params.get("state") != [authorize["state"]]:
    raise RuntimeError("Identita nevrátila autorizaci do účtu správce")
code, _, body = call(endpoint + "/token", {"grant_type": "authorization_code", "client_id": client,
                      "redirect_uri": callback, "code_verifier": verifier, "code": params["code"][0]})
if code != 200:
    raise RuntimeError("Výměna kódu PKCE selhala")
tokens = json.loads(body)
code, _, raw = call(endpoint + "/userinfo", token=tokens["access_token"])
if code != 200 or json.loads(raw).get("preferred_username") != "spravce":
    raise RuntimeError("Chybí potvrzená identita správce")
code, _, _ = call(endpoint + "/logout", {"client_id": client, "refresh_token": tokens["refresh_token"]})
if code != 204:
    raise RuntimeError("Odhlášení uživatele selhalo")
code, _, raw = call(endpoint + "/token", {"client_id": client, "grant_type": "refresh_token",
                                          "refresh_token": tokens["refresh_token"]})
if code != 400 or json.loads(raw).get("error") != "invalid_grant":
    raise RuntimeError("Ukončenou relaci bylo možné obnovit")
print("OIDC Authorization Code s PKCE ověřil správce. UserInfo potvrdilo jeho jméno a odhlášení zneplatnilo obnovovací token.")
