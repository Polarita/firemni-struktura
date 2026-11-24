"""Vydá jednorázové přístupy podle zdrojové IP a spustí skutečný OpenBao Agent uvnitř každé instance."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pristupy as p

CLIENTS = {
    "caddy-test": ("10.239.31.10", 0, 0, "caddy"),
    "headscale-test": ("10.239.31.11", 0, 0, "headscale"),
    "stalwart-mx-test": ("10.239.31.12", 2000, 2000, "stalwart-mx"),
    "reditelstvi-test": ("10.239.32.10", 65534, 65533, "reditelstvi"),
    "vaultwarden-test": ("10.239.33.11", 0, 0, "vaultwarden-agent"),
    "openbao-test": ("10.239.33.10", 986, 986, "openbao-agent"),
}
TARGET = "/opt/polarita-openbao"


def run(*cmd, data=None):
    return subprocess.run(cmd, input=data if data is not None else b"", stdout=subprocess.PIPE,
                          timeout=120, check=True).stdout


def install(name):
    config = json.loads(run("incus", "query", "/1.0/instances/" + name))
    if config["expanded_devices"]["eth0"]["ipv4.address"] != CLIENTS[name][0]:
        raise RuntimeError("Nesouhlasí adresa příjemce " + name)
    for source, dest, mode in [(p.WORK / "bin/bao", "bao", "0755"),
                                (p.WORK / "bin/agent", "agent", "0755"),
                                (p.WORK / "ca.crt", "ca.crt", "0644")]:
        # Hostitel vidí soubor přes namespace běžící instance pouze pro porovnání.
        # Nemá důvěru v symlinky uvnitř instance, pro čtení i zápis používá API Incus.
        remote = f"{name}{TARGET}/{dest}"
        with source.open("rb") as local:
            expected = hashlib.file_digest(local, "sha256").digest()
        pull = subprocess.Popen(["incus", "file", "pull", remote, "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        with pull.stdout as buf:
            actual = hashlib.file_digest(buf, "sha256").digest()
        if pull.wait() or actual != expected:
            run("incus", "file", "push", "-p", "--mode=" + mode, str(source), remote)


def deliver(name, manager):
    ip, uid, gid, fixture = CLIENTS[name]
    base = "auth/approle/role/" + name
    rid = p.request("GET", base + "/role-id", token=manager)["data"]["role_id"]
    cidr = ip + "/32"
    secret = p.request("POST", base + "/secret-id",
                       {"cidr_list": [cidr], "token_bound_cidrs": [cidr]}, manager)["data"]["secret_id"]
    payload = {"role_id": rid, "secret_id": secret, "uid": uid, "gid": gid, "path": fixture}
    run("incus", "exec", "-T", name, "--user", "0", "--group", "0", "--",
        TARGET + "/agent", data=json.dumps(payload).encode())
    token = p.login(p.credentials(name, manager))
    try:
        value = p.request("GET", "test/data/" + fixture, token=token)["data"]["data"]["vzorek"]
    finally:
        p.request("POST", "auth/token/revoke-self", {}, token)
    actual = run("incus", "exec", "-T", name, "--user", str(uid), "--group", str(gid),
                 "--", TARGET + "/agent", "--overit")
    if actual.decode() != hashlib.sha256(value.encode()).hexdigest():
        raise RuntimeError("Příjemce přečetl jinou hodnotu " + name)
    print(f"{name}: OpenBao Agent vykreslil povolené tajemství do /run/secrets.", flush=True)


if __name__ == "__main__":
    if run("hostname", "-s").strip() != b"polarita-hq":
        sys.exit("Úloha patří do polarita-hq")
    os.umask(0o077)
    if (p.WORK / "uzamceno").exists():
        sys.exit(0)
    with (p.WORK / ".agenti-lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if "--install" in sys.argv:
            for name in CLIENTS:
                install(name)
        p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=p.ssl.create_default_context(cafile=str(p.WORK / "ca.crt"))))
        manager = p.login(p.recover("bao-sprava"))
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda n: deliver(n, manager), CLIENTS))
        finally:
            p.request("POST", "auth/token/revoke-self", {}, manager)
