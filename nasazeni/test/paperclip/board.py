"""Přihlášení do nativního Paperclip API přes loopback jeho vlastní instance."""
import http.client
from http.cookies import SimpleCookie
import json
import re
import socket
import sys


class Board:
    def __init__(self, fqdn):
        if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", fqdn) or socket.gethostname().split(".")[0] != "paperclip-test":
            raise ValueError("Přihlášení vyžaduje testovací instance a VPN jméno")
        self.host = fqdn + ":8445"
        self.cookies = {}

    def call(self, method, path, data=None, allowed=(200,)):
        body = json.dumps(data).encode() if data is not None else None
        raw = self.request(method, path, body, "application/json", allowed)
        return json.loads(raw) if raw else None

    def request(self, method, path, body=None, content_type=None, allowed=(200,)):
        if not path.startswith("/api/"):
            raise ValueError("Neznámá cesta Paperclipu")
        connection = http.client.HTTPConnection("127.0.0.1", 3100, timeout=30)
        try:
            headers = {"Host": self.host, "Origin": "https://" + self.host,
                       "Accept": "application/json", "X-Forwarded-Proto": "https"}
            if self.cookies:
                headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            if body is not None:
                headers["Content-Type"] = content_type
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            for header, value in response.getheaders():
                if header.lower() == "set-cookie":
                    cookie = SimpleCookie()
                    cookie.load(value)
                    for key, entry in cookie.items():
                        if entry.value:
                            self.cookies[key] = entry.value
                        else:
                            self.cookies.pop(key, None)
            raw = response.read()
            if response.status not in allowed:
                raise RuntimeError(f"Paperclip odmítl {method} {path} (HTTP {response.status})")
            return raw
        finally:
            connection.close()

    def login(self, password):
        email = "spravce@polarita.test"
        self.call("POST", "/api/auth/sign-in/email", {"email": email, "password": password})
        session = self.call("GET", "/api/auth/get-session")
        if not session or session["user"]["email"] != email or not session["user"]["id"]:
            raise RuntimeError("Relace Paperclipu nepotvrdila správce")
        return session["user"]["id"]


def main():
    board = Board(sys.argv[1])
    action = sys.argv[2]
    if action not in ("vytvor", "prevezmi", "over"):
        raise ValueError("Neznámý krok založení správce")
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise ValueError("Chybí testovací heslo")
    if action == "vytvor":
        board.call("POST", "/api/auth/sign-up/email", {
            "email": "spravce@polarita.test", "name": "Správce TEST", "password": password,
        }, allowed=(200, 201))
        board.cookies.clear()
    user_id = board.login(password)
    if action != "over":
        claim = board.call("POST", "/api/bootstrap/claim", {})
        if claim.get("claimed") is not True or claim.get("userId") != user_id:
            raise RuntimeError("Paperclip nepotvrdil prvního správce")
    companies = board.call("GET", "/api/companies")
    if not isinstance(companies, list):
        raise RuntimeError("Přihlášený správce nemá přístup k seznamu organizací")
    print("Nativní přihlášení Paperclipu potvrdilo testovací účet správce.")


if __name__ == "__main__":
    main()
