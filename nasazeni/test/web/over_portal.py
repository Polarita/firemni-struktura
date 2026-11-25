"""Projde běžné rozhraní ředitelství a zákaznické stránky přes privátní HTTPS."""
import http.cookiejar
from pathlib import Path
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
    assert home.cmp == 1
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    for script in ("souhlas.js", "reklama-test.js"):
        route = "/web-test/" + script
        _, script_headers, source = send(route)
        assert "javascript" in script_headers.get_content_type()
        assert source == (Path(__file__).parent/"public"/script).read_text()
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]/"balicky"/"S3-konfigurator-a-tarify"))
    from pricing import load_price_list, public_price_list
    ceny = public_price_list(load_price_list())
    assert {t["label"]: t["base_monthly_per_object_hellers"]/100 for t in ceny["mrr_tariffs"]} == {
        entry["name"]: entry["offers"]["price"] for entry in home.schema if entry["@type"] == "Service"
    }
    assert "/konfigurator" in home.links and "/web-test/prevzeti-sanonu/" in home.links
    assert send("/konfigurator")[0] == origin+"/konfigurator"
    calculator = "/web-test/kalkulacka-svj/"
    assert calculator in home.links and calculator in send("/konfigurator")[2]
    assert 'name="kwh"' in send(calculator)[2]
    model = {"subjekt":"svj", "revize":"nezjisteno", "kwh":"12000", "cena":"5,50", "procent":"10"}
    data = parse.urlencode(model).encode()
    result = send(calculator, data)[2]
    assert "6600 Kč" in result and "1200 kWh" in result and "Revize nedoložena" in result
    with client.open(request.Request(origin+calculator+"podklad.pdf", data=data, headers={"Origin":origin}), timeout=60) as res:
        pdf = res.read()
        assert res.headers.get_content_type() == "application/pdf" and pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
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
    print("Nová relace správce otevřela ceník, konfigurátor, kalkulačku s ověřenou úsporou a PDF ze sazby Typst i formulář příjmu skenu. Po odhlášení vstup opět vyžádal přihlášení.")


if __name__ == "__main__":
    over(sys.argv[1].rstrip("/"), sys.stdin.readline().rstrip("\r\n"))
