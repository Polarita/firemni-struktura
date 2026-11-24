"""Ověří interní TLS, čtyři aplikační účty, oddělení klíčů a strop paměti na živém Valkey."""
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "trezor"))
import pristupy as p

SERVER = "10.239.33.13"
PORT = 6379


class ResponseError(Exception):
    pass


class Client:
    def __init__(self, tls):
        sock = socket.create_connection((SERVER, PORT), timeout=6)
        self.sock = tls.wrap_socket(sock, server_hostname=SERVER)
        self.stream = self.sock.makefile("rb")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()
        self.sock.close()

    def cmd(self, *args):
        payload = [f"*{len(args)}\r\n".encode()]
        for item in args:
            raw = item.encode()
            payload.extend((f"${len(raw)}\r\n".encode(), raw, b"\r\n"))
        self.sock.sendall(b"".join(payload))
        line = self.stream.readline(8192)
        if not line.endswith(b"\r\n"):
            raise RuntimeError("Neúplná odpověď Valkey")
        value = line[1:-2]
        if line.startswith(b"-"):
            raise ResponseError(value.split(b" ", 1)[0].decode("ascii"))
        if line.startswith(b"+"):
            return value
        if line.startswith(b":"):
            return int(value)
        if line.startswith(b"$"):
            count = int(value)
            if count == -1:
                return None
            if not 0 <= count <= 8192:
                raise RuntimeError("Nečekaná velikost odpovědi")
            data = self.stream.read(count)
            if self.stream.read(2) != b"\r\n":
                raise RuntimeError("Zkrácená odpověď Valkey")
            return data
        raise RuntimeError("Neznámá odpověď Valkey")


def denied(client, reason, *args):
    try:
        client.cmd(*args)
    except ResponseError as error:
        if error.args == (reason,):
            return
        raise
    raise RuntimeError("Valkey povolil cizí operaci")


def main():
    if socket.gethostname().split(".")[0] != "polarita-hq" or os.geteuid() != 0:
        raise SystemExit("Zkouška patří do firemní VM")
    p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=ssl.create_default_context(cafile=str(p.WORK / "ca.crt"))))
    cert = subprocess.check_output(["incus","exec","-T","valkey-test","--","cat","/run/secrets/valkey-cert"], text=True)
    tls = ssl.create_default_context(cadata=cert)
    tls.minimum_version = ssl.TLSVersion.TLSv1_3
    inside = ["incus", "exec", "-T", "valkey-test", "--"]
    cgroup = subprocess.check_output([*inside, "cat", "/sys/fs/cgroup/memory.max"], text=True).strip()
    limit = subprocess.check_output([*inside, "grep", "-x", "maxmemory 32mb", "/etc/polarita-valkey/valkey.conf"], text=True).strip()
    if cgroup != str(144 * 1024 * 1024) or limit != "maxmemory 32mb":
        raise RuntimeError("Chybí paměťový limit instance nebo úložiště klíčů")
    tag = secrets.token_hex(12)
    with Client(tls) as c:
        denied(c, "NOAUTH", "PING")
    manager = p.login(p.recover("bao-sprava"))
    try:
        server = p.login(p.credentials("valkey-test", manager))
        try:
            for name in p.CACHES:
                p.expect_forbidden("GET", "test/data/valkey/" + name, server)
        finally:
            p.request("POST", "auth/token/revoke-self", {}, server)
        for name in p.CACHES:
            token = p.login(p.credentials("cache-" + name, manager))
            try:
                password = p.request("GET", "test/data/valkey/" + name, token=token)["data"]["data"]["heslo"]
                other = next(x for x in p.CACHES if x != name)
                p.expect_forbidden("GET", "test/data/valkey/" + other, token)
            finally:
                p.request("POST", "auth/token/revoke-self", {}, token)
            with Client(tls) as c:
                if c.cmd("AUTH", name, password) != b"OK" or c.cmd("PING") != b"PONG":
                    raise RuntimeError("Ověření účtu selhalo")
                key = f"{name}:test:{tag}"
                if c.cmd("SET", key, tag, "EX", "90") != b"OK" or c.cmd("GET", key) != tag.encode():
                    raise RuntimeError("Aplikační účet neobsloužil vlastní klíč")
                denied(c, "NOPERM", "GET", f"{other}:test:{tag}")
                denied(c, "NOPERM", "CONFIG", "GET", "maxmemory")
                if c.cmd("DEL", key) != 1:
                    raise RuntimeError("Nedokončený testovací úklid")
    finally:
        p.request("POST", "auth/token/revoke-self", {}, manager)
    print("Valkey odmítl anonymní PING. Čtyři účty přes TLS 1.3 zapsaly a přečetly vlastní klíč.")
    print("Cizí klíče, cizí hesla a správní příkazy byly zamítnuty.")


if __name__ == "__main__":
    main()
