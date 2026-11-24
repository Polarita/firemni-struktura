"""Ověří soukromý portál z nové relace a testovací záznam po sobě odstraní."""
import http.cookiejar
import json
import secrets
import subprocess
import sys
from urllib import error, parse, request
from uuid import UUID


def main(origin, password):
    if parse.urlparse(origin).scheme != "https" or not password:
        raise ValueError("Zkouška vyžaduje privátní HTTPS vstup a přihlášení")
    jar = http.cookiejar.CookieJar()
    browser = request.build_opener(request.HTTPCookieProcessor(jar))
    path = "/lhutnik-test/"
    def send(method, dest, body=None, headers=None):
        req = request.Request(origin+dest, data=body, headers=headers or {}, method=method)
        try:
            res = browser.open(req, timeout=12)
        except error.HTTPError as exc:
            res = exc
        with res:
            return res.status, res.geturl(), res.headers, res.read()
    assert send("GET", path)[1] == origin+"/"
    body = parse.urlencode({"username":"spravce","password":password}).encode()
    s, url, _, overview = send("POST","/prihlasit",body, {"Origin":origin})
    assert (s,url) == (200,origin+"/prehled") and b'href="/lhutnik-test/"' in overview
    s, url, _, form = send("GET",path)
    assert (s,url) == (200,origin+path) and b'name="popis"' in form
    s, _, _, js = send("GET",path+"formular.js")
    assert s == 200 and b'If-Match' in js
    route = path+"api/termin"
    label = "TEST-F22-GUI-" + secrets.token_hex(12)
    body = json.dumps({"popis":label,"dny":3,"vyrizeno":False}).encode()
    headers = {"Content-Type":"application/json","Origin":origin}
    assert send("POST",route,body, {**headers, "Origin":"https://jiny.invalid"})[0] == 403
    s, _, meta, raw = send("POST",route,body,headers)
    assert s == 201 and meta["ETag"] == '"1"'
    key = str(UUID(json.loads(raw)["id"]))
    try:
        record = route+"/"+key
        assert send("PUT",record,body,headers)[0] == 428
        s, _, meta, raw = send("PUT",record,body,{**headers,"If-Match":'"1"'})
        assert s == 200 and meta["ETag"] == '"2"' and json.loads(raw)["id"] == key
        assert send("PUT",record,body,{**headers,"If-Match":'"1"'})[0] == 412
        assert send("POST","/odhlasit",b"",{"Origin":origin})[1] == origin+"/"
        assert send("GET",record)[1] == origin+"/"
        assert send("PUT",record,body,{**headers,"If-Match":'"2"'})[0] == 401
    finally:
        cmd = ["sudo","-n","incus","exec","-T","--project","polarita","polarita-hq","--",
               "incus","exec","-T","postgres-test","--","runuser","-u","postgres","--",
               "psql","-XqAtw","-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik"]
        subprocess.run(cmd, input=f"DELETE FROM polarita_test_metadata.meta_termin WHERE id='{key}' AND popis='{label}';",
                       text=True, check=True)
    print("Přihlášení přes ředitelství otevřelo formulář, změna vyžadovala správný ETag a po odhlášení API opět odmítlo zápis.")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"), sys.stdin.readline().rstrip("\n"))
