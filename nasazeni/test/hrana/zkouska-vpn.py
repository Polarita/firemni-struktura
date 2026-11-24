"""Ověří čistou registraci dvou klientů vlastního Headscale a jejich vzájemné spojení."""
import json
from contextlib import ExitStack
from pathlib import Path
import secrets
import subprocess
import sys
import time


def run(*args, data=None, timeout=90):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE,
                          check=True, timeout=timeout).stdout


def inside(name, *args, data=None):
    return run("incus", "exec", "-T", name, "--", *args, data=data)


def hs(*args):
    return inside("headscale-test", "/ko-app/headscale", *args, "-o", "json")


def remove_client(name):
    try:
        run("incus", "delete", "--force", name, timeout=180)
    except subprocess.TimeoutExpired:
        # Démon může po odpojení klienta stále dokončovat tutéž operaci.
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if name not in run("incus", "list", name, "-c", "n", "-f", "csv").decode().splitlines():
                return
            time.sleep(3)
        raise


def delete_nodes(user_id):
    for node in json.loads(hs("nodes", "list")) or []:
        if str(node["user"]["id"]) == str(user_id):
            hs("nodes", "delete", "-i", str(node["id"]), "--force")


def connect(name, user_id, ca, clients):
    # Alpine zakládá /run při bootu. Testovací přístup ukládáme až na tmpfs.
    inside(name, "sh", "-ec", """
        for i in $(seq 1 30); do
            if grep -q ' /run tmpfs ' /proc/mounts; then exit 0; fi
            sleep 1
        done
        exit 1
    """)
    for binary in ("tailscale", "tailscaled"):
        run("incus", "file", "push", "--mode=0755", str(clients / binary),
            f"{name}/usr/local/bin/{binary}")
    run("incus", "file", "push", "--mode=0644", "-", f"{name}/run/polarita-ca.crt", data=ca)
    inside(name, "sh", "-eu", "-c", """
        cat /run/polarita-ca.crt >>/etc/ssl/certs/ca-certificates.crt
        for i in $(seq 1 20); do
            wget -qO /dev/null https://vpn.polarita.test:8443/health 2>/dev/null && exit 0
            sleep 1
        done
        exit 1
    """)
    cfg = {"version": "alpha0", "serverURL": "https://vpn.polarita.test:8443",
           "authKey": "file:/run/registrace", "acceptDNS": False, "hostname": name}
    run("incus", "file", "push", "--mode=0600", "-", f"{name}/run/klient.json",
        data=json.dumps(cfg).encode())
    for attempt in range(3):
        key = json.loads(hs("preauthkeys", "create", "--user", str(user_id),
                            "--expiration", "5m"))["key"]
        run("incus", "file", "push", "--mode=0600", "-", f"{name}/run/registrace", data=key.encode())
        inside(name, "sh", "-eu", "-c", """
            export SSL_CERT_FILE=/run/polarita-ca.crt TS_NO_LOGS_NO_SUPPORT=true
            tailscaled --config=/run/klient.json --tun=userspace-networking --state=/run/tailscaled.state >/run/test-vpn.log 2>&1 </dev/null &
            echo $! >/run/test-vpn.pid
        """)
        status = {}
        try:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                try:
                    result = subprocess.run(["incus", "exec", "-T", name, "--", "tailscale", "status", "--json"],
                                            capture_output=True, timeout=20)
                except subprocess.TimeoutExpired:
                    continue
                status = json.loads(result.stdout or "{}")
                if status.get("BackendState") == "Running":
                    break
                if "authkey already used" in " ".join(status.get("Health") or []):
                    break
                time.sleep(1)
        finally:
            inside(name, "rm", "-f", "/run/registrace")
        if status.get("BackendState") == "Running":
            break
        if "authkey already used" not in inside(name, "cat", "/run/test-vpn.log").decode(errors="replace"):
            raise RuntimeError(f"Klient {name} se nepřipojil")
        print(f"{name}: server spotřeboval klíč před dokončením registrace (pokus {attempt+1})", flush=True)
        inside(name, "sh", "-ec", 'kill "$(cat /run/test-vpn.pid)"; for i in $(seq 1 10); do [ ! -S /var/run/tailscale/tailscaled.sock ] && exit 0; sleep 1; done; exit 1')
    else:
        raise RuntimeError(f"Registrace {name} selhala po třech jednotlivých klíčích")
    if status["Self"]["DNSName"] != f"{name}.int.polarita.test.":
        raise ValueError(f"Registrace nebo MagicDNS neodpovídá pro {name}")
    return next(ip for ip in status["TailscaleIPs"] if ":" not in ip)


def main(clients):
    if run("hostname", "-s").strip() != b"polarita-hq":
        raise SystemExit("Ověření patří do VM polarita-hq")
    ca = inside("caddy-test", "cat", "/data/caddy/pki/authorities/local/root.crt")
    group = "zkouska-" + secrets.token_hex(4)
    with ExitStack() as cleanup:
        user_id = json.loads(hs("users", "create", group))["id"]
        cleanup.callback(hs, "users", "destroy", "-i", str(user_id), "--force")
        cleanup.callback(delete_nodes, user_id)
        names = [group + "-a", group + "-b"]
        ips = []
        for name in names:
            run("incus", "init", "images:alpine/3.24", name, "-p", "default", "-p", "dmz_edge",
                "-c", "user.polarita.role=docasny-klient-vpn")
            cleanup.callback(remove_client, name)
            run("incus", "start", name)
            ips.append(connect(name, user_id, ca, clients))
        for i, name in enumerate(names):
            peers = json.loads(inside(name, "tailscale", "debug", "derp-map"))
            if set(peers["Regions"]) != {"999"}:
                raise ValueError("Klient má přístup k nečekanému DERP regionu")
            for attempt in range(5):
                try:
                    result = inside(name, "tailscale", "ping", "--until-direct=false",
                                    "--c=1", "--timeout=4s", ips[1-i])
                    break
                except subprocess.CalledProcessError:
                    if attempt == 4:
                        raise
                    time.sleep(1)
            print(result.decode().strip())
            print(f"{name}: registrace, MagicDNS a vlastní mapa DERP ověřeny")
        # Přímou cestu odpojíme jen uvnitř obou dočasných klientů.
        lan = []
        for name in names:
            instance = json.loads(run("incus", "list", name, "-f", "json"))[0]
            addresses = instance["state"]["network"]["eth0"]["addresses"]
            lan.append(next(a["address"] for a in addresses if a["family"] == "inet"))
        for i, name in enumerate(names):
            peer_lan = lan[1 - i]
            inside(name, "ip", "route", "add", "unreachable", peer_lan + "/32")
        for _ in range(12):
            ping = subprocess.run(["incus", "exec", "-T", names[0], "--", "tailscale", "ping",
                                   "--until-direct=false", "--c=1", "--timeout=3s", ips[1]],
                                  capture_output=True, timeout=10)
            if ping.returncode == 0 and b"via DERP(polarita)" in ping.stdout:
                print(ping.stdout.decode().strip())
                break
            time.sleep(1)
        else:
            raise RuntimeError("Po odebrání přímé cesty chybí potvrzená odpověď přes DERP")
        check = json.loads(inside(names[0], "tailscale", "netcheck", "--format=json"))
        if not check.get("UDP") or check.get("PreferredDERP") != 999:
            raise ValueError("Klient nepotvrdil funkční STUN a vlastní DERP")
        print("STUN přes UDP a vlastní DERP 999 ověřeny")
    if any(str(u["id"]) == str(user_id) for u in json.loads(hs("users", "list")) or []):
        raise RuntimeError("Zůstal zkušební účet")
    print("Systém odstranil dočasné klienty, uzly, registrační klíče i účet zkoušky")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
