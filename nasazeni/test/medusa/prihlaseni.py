"""Ověří stejnou identitu přes běžné HTTP rozhraní e-shopu v TEST."""
import http.client
import json
import re
import ssl
import sys

host = sys.argv[1]
if host == "127.0.0.1":
    connect = lambda: http.client.HTTPConnection(host,9000,timeout=35)
elif re.fullmatch(r"[a-z0-9-]+(?:[.][a-z0-9-]+)+[.]ts[.]net",host):
    connect = lambda: http.client.HTTPSConnection(host,8450,timeout=45,context=ssl.create_default_context())
else:
    sys.exit("Neočekávaný název přihlašovacího serveru.")

def call(method, path, status, body=None, token=None):
    headers = {"Content-Type":"application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = "Bearer "+token
    conn = connect()
    try:
        conn.request(method,path,json.dumps(body).encode() if body is not None else None,headers)
        res=conn.getresponse()
        if res.status!=status:
            raise RuntimeError(f"Rozhraní {method} {path} vrátilo HTTP {res.status}, očekáváno {status}.")
        data=res.read(1<<20)
        return json.loads(data) if status==200 and "application/json" in res.getheader("Content-Type","") else data
    finally:
        conn.close()

email="spravce@polarita.test"
call("GET","/admin/users/me",401)
token=call("POST","/auth/user/emailpass",200,{"email":email,"password":sys.stdin.readline().rstrip("\r\n")})["token"]
if call("GET","/admin/users/me",200,token=token)["user"]["email"] != email:
    sys.exit("Nesouhlasí přihlášený účet.")
call("GET","/admin/sklad/bubny?stitek=NEEXISTUJE-TEST-2fa26631",404,token=token)
print("Správce se svým testovacím heslem otevřel vlastní účet Medusy. Anonymní profil byl odmítnut.")
