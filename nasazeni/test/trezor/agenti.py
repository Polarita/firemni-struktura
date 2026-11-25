"""Vydá jednorázové přístupy podle zdrojové IP a spustí skutečný OpenBao Agent uvnitř každé instance."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
import pristupy as p

CLIENTS = {
    "caddy-test": ("10.239.31.10", 0, 0, "caddy"),
    "headscale-test": ("10.239.31.11", 0, 0, "headscale"),
    "stalwart-mx-test": ("10.239.31.12", 2000, 2000, "stalwart-mx"),
    "reditelstvi-test": ("10.239.32.10", 65534, 65533, "reditelstvi"),
    "vaultwarden-test": ("10.239.33.11", 0, 0, "vaultwarden-agent"),
    "pecet-test": ("10.239.32.12", 65534, 65534, "pecet-agent"),
    "keycloak-test": ("10.239.32.11", 1000, 0, "keycloak-agent"),
    "paperless-test": ("10.239.32.21", 0, 0, "paperless-agent"),
    "medusa-test": ("10.239.32.23", 17309, 17309, "medusa-agent"),
    "umami-test": ("10.239.32.22", 1001, 1001, "umami-agent"),
    "vikunja-test": ("10.239.32.20", 17320, 17320, "vikunja-agent"),
    "paperclip-test": ("10.239.32.18", 17308, 17308, "paperclip-agent"),
    "zulip-test": ("10.239.32.16", 0, 0, "zulip-agent"),
    "zulip-fronta-test": ("10.239.32.17", 0, 0, "zulip-fronta-agent"),
    "gitea-test": ("10.239.32.13", 17307, 17307, "gitea-agent"),
    "garage-test": ("10.239.33.14", 17306, 17306, "garage-agent"),
    "valkey-test": ("10.239.33.13", 999, 999, "valkey-agent"),
    "postgres-test": ("10.239.33.12", 0, 0, "postgres-agent"),
    "openbao-test": ("10.239.33.10", 986, 986, "openbao-agent"),
}
TARGET = "/opt/polarita-openbao"


def run(*cmd, data=None):
    return subprocess.run(cmd, input=data if data is not None else b"", stdout=subprocess.PIPE,
                          timeout=120, check=True).stdout


def install(name, files):
    config = json.loads(run("incus", "query", "/1.0/instances/" + name))
    if config["expanded_devices"]["eth0"]["ipv4.address"] != CLIENTS[name][0]:
        raise RuntimeError("Nesouhlasí adresa příjemce " + name)
    for source, dest, mode, expected in files:
        remote = f"{name}{TARGET}/{dest}"
        pull = subprocess.Popen(["incus", "file", "pull", remote, "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        with pull.stdout as buf:
            actual = hashlib.file_digest(buf, "sha256").digest()
        if pull.wait() or actual != expected:
            run("incus", "file", "push", "-p", "--mode=" + mode, str(source), remote)


def deliver(name, manager):
    ip, uid, gid, fixture = CLIENTS[name]
    if name == "umami-test":
        run("incus", "exec", "-T", name, "--user", "0", "--group", "0", "--",
            "sh", "/etc/polarita-umami/db-host.sh")
    base = "auth/approle/role/" + name
    rid = p.request("GET", base + "/role-id", token=manager)["data"]["role_id"]
    cidr = ip + "/32"
    secret = p.request("POST", base + "/secret-id",
                       {"cidr_list": [cidr], "token_bound_cidrs": [cidr]}, manager)["data"]["secret_id"]
    payload = {"role_id": rid, "secret_id": secret, "uid": uid, "gid": gid, "path": fixture,
               "databases": p.DATABASE_ACCESS.get(name, ()), "seal": name == "pecet-test",
               "medusa": name == "medusa-test", "umami": name == "umami-test", "paperless": name == "paperless-test", "paperclip": name == "paperclip-test", "vikunja": name == "vikunja-test",
               "zulip": name == "zulip-test", "zulip_queue": name in ("zulip-test","zulip-fronta-test"),
               "gitea": name == "gitea-test", "garage": name == "garage-test", "caches": p.CACHES if name == "valkey-test" else []}
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


def deliver_with_token(name, credentials):
    for attempt in range(2):
        try:
            if attempt:
                # Na pomalém disku načti binárku před vydáním krátkodobého přístupu.
                run("incus", "exec", "-T", name, "--", TARGET + "/bao", "version")
            manager = p.login(credentials)
            try:
                deliver(name, manager)
            finally:
                p.request("POST", "auth/token/revoke-self", {}, manager)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError, ConnectionError, URLError) as exc:
            cause = exc.reason if isinstance(exc, URLError) else exc
            timed_out = isinstance(cause, (TimeoutError, ConnectionError, subprocess.TimeoutExpired))
            agent_timeout = isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 75
            if attempt or not (timed_out or agent_timeout):
                raise
        print(f"{name}: spojení nebo vykreslení překročilo limit, opakuji předání s novým přístupem.", flush=True)
        time.sleep(3)


if __name__ == "__main__":
    if run("hostname", "-s").strip() != b"polarita-hq":
        sys.exit("Úloha patří do polarita-hq")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--klient", choices=sorted(CLIENTS))
    parser.add_argument("--spoustec", type=Path, default=p.WORK / "bin/agent")
    options = parser.parse_args()
    clients = [options.klient] if options.klient else CLIENTS
    os.umask(0o077)
    if (p.WORK / "uzamceno").exists():
        sys.exit(0)
    with (p.WORK / ".agenti-lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if options.install:
            files = []
            for source, dest, mode in ((p.WORK / "bin/bao", "bao", "0755"),
                                       (options.spoustec, "agent", "0755"), (p.WORK / "ca.crt", "ca.crt", "0644")):
                with source.open("rb") as local:
                    files.append((source, dest, mode, hashlib.file_digest(local, "sha256").digest()))
            for name in clients:
                install(name, files)
        p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=p.ssl.create_default_context(cafile=str(p.WORK / "ca.crt"))))
        credentials = p.recover("bao-sprava")
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda name: deliver_with_token(name, credentials), clients))
