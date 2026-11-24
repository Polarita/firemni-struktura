"""Kontrola povoleného HTTPS a izolace z účtu pracovníka CI."""
from http.client import HTTPSConnection
import socket
import ssl
import sys

host = sys.argv[1]
ctx = ssl.create_default_context(cafile="/etc/polarita-gitea/git-ca.crt")
c = HTTPSConnection(host, context=ctx, timeout=8)
c.request("GET", "/identita/realms/polarita/.well-known/openid-configuration")
response = c.getresponse()
if response.status != 404:
    raise RuntimeError("Pracovník CI má přístup k cestě pro strojovou identitu")
response.read()
c.close()
for ip, port in [("10.239.32.11", 8080), ("10.239.33.12", 5432), ("10.239.33.10", 8200), ("192.0.2.1", 443)]:
    try:
        s = socket.create_connection((ip,port), timeout=2)
    except OSError:
        continue
    s.close()
    raise RuntimeError("Ze sítě runneru je dostupný nepovolený cíl")
print("CI ověřilo TLS Gitu. Identita, databáze, trezor a vnější síť zůstaly oddělené.")
