"""Ověření identity Headscale při startu z uložené konfigurace, databáze a strojových klíčů."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


BINARY_HASH = "e827fc9b12d958bc95b081c4401dd63f8e0471d025b45b508535a920532150a8"


def key_digest(origin):
    # Strojový veřejný klíč vrací původní protokol klientům při navázání VPN.
    client = build_opener(ProxyHandler({}))
    with client.open(origin + "/key?v=200", timeout=2) as response:
        key = json.load(response)["publicKey"]
    if not re.fullmatch("mkey:[0-9a-f]{64}", key):
        raise ValueError("Neplatný veřejný klíč Headscale")
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def check_binary(binary):
    with binary.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != BINARY_HASH:
            raise RuntimeError("Nesouhlasí otisk obnovovacího programu Headscale 0.29.7")


def collect(target):
    binary = target / "headscale-program"
    subprocess.run(["incus", "file", "pull", "headscale-test/ko-app/headscale", str(binary)], check=True)
    check_binary(binary)
    (target / "headscale-identita.sha256").write_text(key_digest("http://10.239.31.11:8080") + "\n")


def verify(target, local):
    # Kontrola se smí spustit jen v izolované síti, i když má obnovený server původní identitu.
    if os.listdir("/sys/class/net") != ["lo"]:
        raise RuntimeError("Obnova identity VPN potřebuje vlastní síť pouze s loopbackem")
    source = target / "headscale-program"
    check_binary(source)
    binary = local / "headscale"
    shutil.copyfile(source, binary)
    binary.chmod(0o700)
    config_dir = target / "hrana/headscale"
    for name in ("derp.yaml", "policy.hujson"):
        shutil.copyfile(config_dir / name, local / name)
    config = (config_dir / "config.yaml").read_text()
    config = config.replace("/var/lib/headscale/", str(local) + "/")
    config = config.replace("/etc/headscale/", str(local) + "/").replace("10.239.31.11:", "127.0.0.1:")
    conf = local / "config.yaml"
    conf.write_text(config)
    origin = "http://127.0.0.1:8080"
    expected = (target / "headscale-identita.sha256").read_text().strip()
    with subprocess.Popen([binary, "serve", "--config", conf], cwd=local,
                          env={**os.environ, "GOMAXPROCS":"2"}, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as server:
        try:
            for _ in range(80):
                if server.poll() is not None:
                    raise RuntimeError("Obnovený Headscale ukončil start")
                try:
                    digest = key_digest(origin)
                    break
                except URLError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Obnovený Headscale včas neodpověděl")
            if digest != expected:
                raise RuntimeError("Obnovená VPN nabízí odlišnou identitu")
            with build_opener(ProxyHandler({})).open(origin + "/health", timeout=3) as response:
                if json.load(response).get("status") != "pass":
                    raise RuntimeError("Obnovený Headscale není připraven")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
    print("Headscale obnovil na izolovaném loopbacku původní veřejnou identitu a odpověděl na kontrolu služby.")
