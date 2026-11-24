"""Přihlásí správce přes veřejný TEST vstup do Gitea ve vlastní nové relaci."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import sys
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

origin = sys.argv[1].rstrip("/")
base = urlsplit(origin)
if base.scheme != "https" or base.path or not base.hostname:
    raise SystemExit("Chybný vstup ředitelství")


class SameOrigin(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl)[:2] != base[:2]:
            raise RuntimeError("Přihlášení opustilo doménu ředitelství")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Login(HTMLParser):
    action = None
    account = None
    def handle_starttag(self,tag,attrs):
        field = dict(attrs)
        if tag == "form" and field.get("id") == "kc-form-login":
            self.action = field["action"]
        if tag == "input" and field.get("name") == "email":
            self.account = field.get("value")


def main():
    web = build_opener(SameOrigin(), HTTPCookieProcessor(CookieJar()))
    def visit(url, fields=None):
        if urlsplit(url)[:2] != base[:2]:
            raise RuntimeError("Nepovolený cíl formuláře")
        req = Request(url, data=urlencode(fields).encode() if fields is not None else None,
                      headers={"Origin":origin,"Referer":origin+"/git/"})
        with web.open(req,timeout=20) as res:
            page = Login()
            page.feed(res.read().decode())
            return urlsplit(res.url).path,page
    _,page = visit(origin+"/git/user/oauth2/keycloak")
    if not page.action:
        raise RuntimeError("Chybí přihlášení Keycloaku pro Gitea")
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise RuntimeError("Chybí testovací heslo")
    path,_ = visit(urljoin(origin,page.action), {"username":"spravce","password":password})
    if not path.startswith("/git/"):
        raise RuntimeError("Nedokončený návrat do Gitea")
    path,page = visit(origin+"/git/user/settings")
    if path.rstrip("/") != "/git/user/settings" or page.account != "spravce@polarita.test":
        raise RuntimeError("Profil Gitea nepotvrdil testovacího správce")
    print("Nová relace ředitelství přihlásila správce do Gitea přes Keycloak a ověřila jeho vlastní profil.")


if __name__ == "__main__":
    main()
