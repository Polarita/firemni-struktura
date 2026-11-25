"""Zkouška příjmu logů, místního rozhodnutí a odblokování jediného testovacího klienta."""
from contextlib import ExitStack
import ipaddress
import json
import secrets
import subprocess
import time
from urllib.request import urlopen

WORK = "/srv/polarita/infra/crowdsec-test"
SCENARIO = "polarita/opakovane-odmitnuti"
# Lokální exportér při studeném startu sdílí procesor s karanténou.
HTTP_TIMEOUT = 30


def run(*args, data=None, timeout=90, check=True):
    return subprocess.run(args, input=data, capture_output=True, timeout=timeout, check=check)


def cli(*args):
    return run(f"{WORK}/bin/cscli", "-c", f"{WORK}/conf/config.yaml", *args)


def in_set(ip):
    result = run("nft", "get", "element", "ip", "polarita_crowdsec", "blokovane",
                 "{", ip, "}", check=False)
    if result.returncode and b"No such file or directory" not in result.stderr:
        raise RuntimeError(result.stderr.decode())
    return result.returncode == 0


def smtp(name, commands):
    return run("incus", "exec", "-T", name, "--", "timeout", "12", "nc", "-w", "4",
               "10.239.31.12", "25", data=commands.encode("ascii"), check=False).stdout


def parsed_http():
    with urlopen("http://127.0.0.1:18281/metrics", timeout=HTTP_TIMEOUT) as response:
        metrics = response.read().decode().splitlines()
    return sum(float(line.rsplit(" ", 1)[1]) for line in metrics
               if line.startswith("cs_node_hits_ok_total{")
               and 'name="polarita/caddy"' in line and '/reditelstvi.json"' in line)


def main():
    before = parsed_http()
    with urlopen("http://127.0.0.1:18184/", timeout=HTTP_TIMEOUT) as response:
        if response.status != 200 or "polarita-caddy" not in response.headers.get("Via", ""):
            raise RuntimeError("Zkouška HTTP neprošla přes firemní Caddy")
    for _ in range(10):
        if parsed_http() > before:
            break
        time.sleep(1)
    else:
        raise RuntimeError("CrowdSec nezpracoval nový HTTP záznam ředitelství")
    print("CrowdSec přečetl nový záznam HTTP z Caddy.", flush=True)

    name = "zkouska-mx-" + secrets.token_hex(4)
    with ExitStack() as cleanup:
        run("incus", "init", "images:alpine/3.24", name, "-p", "default", "-p", "dmz_edge",
            "-c", "user.polarita.role=docasna-zkouska-ochrany")
        cleanup.callback(run, "incus", "delete", "-f", name)
        run("incus", "start", name)
        for _ in range(40):
            state = json.loads(run("incus", "query", f"/1.0/instances/{name}/state").stdout)
            addresses = state.get("network", {}).get("eth0", {}).get("addresses", [])
            ips = [a["address"] for a in addresses if a["family"] == "inet"]
            if ips:
                break
            time.sleep(1)
        if len(ips) != 1 or ipaddress.ip_address(ips[0]) not in ipaddress.ip_network("10.239.31.0/24"):
            raise RuntimeError("Klient nemá vlastní adresu na mostu DMZ")
        ip = ips[0]
        if in_set(ip):
            raise RuntimeError("Přidělená adresa již má existující rozhodnutí")
        if not smtp(name, "QUIT\r\n").startswith(b"220"):
            raise RuntimeError("Zkušební klient se nepřipojil k SMTP")
        print(f"{name} ({ip}): připojení před zkouškou prošlo.", flush=True)
        def release():
            cli("decisions", "delete", "--ip", ip, "--scenario", SCENARIO, "--origin", "crowdsec")
        cleanup.callback(release)

        for attempt in range(12):
            if in_set(ip):
                break
            recipient = f"{name}-{attempt}@example.invalid"
            reply = smtp(name, "EHLO zkouska.polarita.test\r\nMAIL FROM:<>\r\n"
                         f"RCPT TO:<{recipient}>\r\nQUIT\r\n")
            if b"550 " not in reply and not in_set(ip):
                raise RuntimeError(f"Chybí odmítnutí testovací adresy: {reply[:180]!r}")
        for _ in range(15):
            if in_set(ip):
                break
            time.sleep(1)
        else:
            raise RuntimeError("Rozhodnutí se nepropsalo do místní sady nftables")
        decisions = json.loads(cli("decisions", "list", "-o", "json", "--ip", ip).stdout)
        if not any(d["scenario"] == SCENARIO and d["origin"] == "crowdsec" and d["value"] == ip
                   for alert in decisions for d in alert["decisions"]):
            raise RuntimeError("Chybí automatické rozhodnutí testovaného scénáře")
        if smtp(name, "QUIT\r\n").startswith(b"220"):
            raise RuntimeError("Blokovaný klient se připojil k SMTP")
        print("Odmítnutí z protokolu SMTP vyvolala rozhodnutí CrowdSec. Firewall zablokoval nové spojení.", flush=True)
        release()
        for _ in range(15):
            if not in_set(ip):
                break
            time.sleep(1)
        if in_set(ip) or not smtp(name, "QUIT\r\n").startswith(b"220"):
            raise RuntimeError("Přístup po odebrání rozhodnutí nebyl obnoven")
        print("Po odblokování klient znovu obdržel pozdrav SMTP 220.", flush=True)


if __name__ == "__main__":
    if run("hostname", "-s").stdout.strip() != b"polarita-hq":
        raise SystemExit("Zkouška se spouští ve firemní VM")
    main()
