"""Nastaví důvěrné OIDC přes místní administrační formulář bez hesla v argv."""
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import json
import re
import ssl
import sys
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, HTTPSHandler, HTTPCookieProcessor, ProxyHandler, Request


class Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.links = {}

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "input" and fields.get("type") == "hidden" and fields.get("name") == "_csrf":
            self.hidden["_csrf"] = fields.get("value","")
        if tag == "a":
            self.current = fields.get("href","")

    def handle_endtag(self, tag):
        if tag == "a":
            self.current = ""

    def handle_data(self, data):
        if getattr(self,"current","") and data.strip():
            self.links.setdefault(self.current, []).append(data.strip())


def main():
    config = json.load(sys.stdin)
    origin = config["origin"]
    base = origin+"/git"
    class SameOrigin(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urlsplit(newurl)[:2] != urlsplit(origin)[:2]:
                raise RuntimeError("Nečekané přesměrování správy Gitea")
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    ssl_ctx = ssl.create_default_context(cafile="/etc/polarita-gitea/git-ca.crt")
    web = build_opener(ProxyHandler({}), SameOrigin(), HTTPSHandler(context=ssl_ctx), HTTPCookieProcessor(CookieJar()))
    def page(path, data=None):
        req = Request(base+path, data=urlencode(data).encode() if data is not None else None,
                      headers={"Origin":origin,"Referer":base+path,"Accept-Language":"en-US"})
        with web.open(req, timeout=25) as res:
            form = Form()
            form.feed(res.read().decode())
            return urlsplit(res.url).path, form
    login = "/user/login"
    _, form = page(login)
    page(login, {**form.hidden,"user_name":config["admin"],"password":config["password"]})
    auth = "/-/admin/auths"
    location, form = page(auth)
    if location != "/git"+auth:
        raise RuntimeError("Gitea odmítla přístup k nastavení identity na "+location)
    links = [urlsplit(urljoin(base+auth,href)).path for href,parts in form.links.items() if "keycloak" in parts]
    target = auth+"/new"
    if links:
        if len(links)!=1 or not re.fullmatch(r"/git/-/admin/auths/[0-9]+",links[0]):
            raise RuntimeError("Nejednoznačný zdroj přihlášení")
        target = links[0][4:]
    _, form = page(target)
    fields = {**form.hidden,"name":"keycloak","type":"6","oauth2_provider":"openidConnect","oauth2_key":"gitea",
              "oauth2_secret":config["key"],"open_id_connect_auto_discovery_url":origin+"/identita/realms/polarita/.well-known/openid-configuration",
              "oauth2_scopes":"openid,email,profile","is_active":"on"}
    location, _ = page(target,fields)
    _, listing = page(auth)
    if not any("keycloak" in parts for parts in listing.links.values()):
        raise RuntimeError("Gitea nepotvrdila zdroj přihlášení na "+location)


if __name__ == "__main__":
    main()
