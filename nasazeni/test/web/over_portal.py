"""Projde běžné rozhraní ředitelství a zákaznické stránky přes privátní HTTPS."""
import http.cookiejar
import sys
from urllib import error, parse, request
from over import Stranka


def over(origin, password):
    if parse.urlsplit(origin).scheme != "https" or not password:
        raise ValueError("Zkouška vyžaduje privátní HTTPS vstup a přihlášení")
    client = request.build_opener(request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def send(path, data=None):
        req = request.Request(origin+path, data=data, headers={"Origin":origin})
        with client.open(req, timeout=90) as res:
            return res.geturl(), res.headers, res.read().decode()

    assert send("/web-test/")[0] == origin+"/"
    url, _, overview = send("/prihlasit", parse.urlencode({"username":"spravce","password":password}).encode())
    assert url == origin+"/prehled" and 'href="/web-test/"' in overview
    home, intake = Stranka(), Stranka()
    url, headers, html = send("/web-test/")
    assert url == origin+"/web-test/" and "noindex" in headers["X-Robots-Tag"]
    home.feed(html)
    assert {"Start SVJ", "Standard Objekt", "Maxi Areál / B2B"} == {v["name"] for v in home.schema if v["@type"] == "Service"}
    assert "/konfigurator" in home.links and "/web-test/prevzeti-sanonu/" in home.links
    assert send("/konfigurator")[0] == origin+"/konfigurator"
    intake.feed(send("/web-test/prevzeti-sanonu/")[2])
    assert "/lhutnik-test/spisy" in intake.links and 'id="sanony"' in send("/lhutnik-test/spisy")[2]
    assert "/web-test/prevzeti-sanonu/" in send("/web-test/llms.txt")[2]
    try:
        send("/web-test/package-lock.json")
    except error.HTTPError as exc:
        assert exc.code == 404
    else:
        raise RuntimeError("Server zpřístupnil interní soubor sestavení.")
    send("/odhlasit", b"")
    assert send("/web-test/llms.txt")[0] == origin+"/"
    print("Nová relace správce otevřela ceník, konfigurátor a formulář příjmu PDF. Po odhlášení vstup opět vyžádal přihlášení.")


if __name__ == "__main__":
    over(sys.argv[1].rstrip("/"), sys.stdin.readline().rstrip("\r\n"))
