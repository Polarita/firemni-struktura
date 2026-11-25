"""Ověří tlačítko a obě podoby odhlášení po HTTPS bez přihlášení či přesměrování."""
import email
from email import policy
import http.client
import re
import secrets
import sys
from urllib.parse import urlsplit

host = sys.argv[1]
msg = email.message_from_binary_file(sys.stdin.buffer, policy=policy.default)
link = urlsplit(str(msg["List-Unsubscribe"])[1:-1])
assert link.scheme == "https" and link.netloc == host and not link.query and not link.fragment
assert re.fullmatch(r"/ecomail-test/odhlaseni/[A-Za-z0-9_-]{43}", link.path)
assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
assert link.geturl() in msg.get_body().get_content()

def request(method, path, status, body=None, content_type=None):
    conn = http.client.HTTPSConnection(host, timeout=35)
    try:
        conn.request(method, path, body, {"Content-Type": content_type} if content_type else {})
        res = conn.getresponse()
        data = res.read(4096)
        if res.status != status or res.getheader("Set-Cookie") or res.getheader("Location"):
            raise RuntimeError(f"{method} vrátil {res.status}, očekáváno {status} bez relace a přesměrování.")
        return data
    finally:
        conn.close()

wrong = "/ecomail-test/odhlaseni/" + secrets.token_urlsafe(32)
form = "application/x-www-form-urlencoded"
request("POST", wrong, 404, "List-Unsubscribe=One-Click", form)
assert b'<form method="post">' in request("GET",link.path,200)
request("HEAD",link.path,200)
request("POST",link.path,400,"List-Unsubscribe=Wrong",form)
if sys.argv[2] == "nahled":
    print("Náhled bez přihlášení a HEAD fungují. Chybný token i formulář byly odmítnuty.")
elif sys.argv[2] == "odhlasit":
    result = request("POST",link.path,200,"List-Unsubscribe=One-Click",form)
    assert "Odhlášení potvrzeno".encode() in result
    multipart = '--test\r\nContent-Disposition: form-data; name="List-Unsubscribe"\r\n\r\nOne-Click\r\n--test--\r\n'
    assert request("POST",link.path,200,multipart,"multipart/form-data; boundary=test") == result
    print("Odhlášení i opakování přes HTTPS prošlo bez účtu. Podpis DKIM a vazba odkazu na zprávu ověřeny.")
else:
    raise ValueError("Neznámá zkouška")
