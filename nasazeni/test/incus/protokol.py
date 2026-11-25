"""Přečte skutečnou topologii druhého bloku uvnitř jediné firemní VM."""
import json
from pathlib import Path
import shutil
import socket
import subprocess


def query(path):
    return json.loads(subprocess.check_output(["incus", "query", "/1.0"+path]))


def over():
    if socket.gethostname().split(".")[0] != "polarita-hq":
        raise RuntimeError("Zkouška patří do VM ředitelství.")
    if shutil.which("docker") or Path("/run/docker.sock").exists():
        raise RuntimeError("VM používá další kontejnerový runtime.")
    if query("/storage-pools/default")["config"]["source"] != "polarita_zfs/data/incus/pool":
        raise RuntimeError("Nesouhlasí úložiště vnitřního Incusu.")
    bridges = ("app_internal", "data_vault", "dmz_edge")
    for name in bridges:
        network = query("/networks/"+name)
        nic = query("/profiles/"+name)["devices"]["eth0"]
        if not (network["managed"] and network["type"] == "bridge" and nic["type"] == "nic"
                and nic["network"] == name):
            raise RuntimeError("Profil není připojen k deklarovanému mostu.")
    airgap = query("/profiles/sandbox_airgap")["devices"]
    if airgap.get("eth0", {}).get("type") != "none" or any(d["type"] == "nic" for d in airgap.values()):
        raise RuntimeError("Izolovaný profil má síťové rozhraní.")
    instances = query("/instances?recursion=1")
    containers = [x for x in instances if x["type"] == "container"]
    if not any(x["name"] == "reditelstvi-test" and x["status"] == "Running" for x in containers):
        raise RuntimeError("Vnitřní instance ředitelství neběží.")
    if any(x["expanded_config"].get("security.privileged", "false").lower() not in ("false","0","no","off")
           for x in containers):
        raise RuntimeError("Vnitřní Incus obsahuje privilegovaný kontejner.")
    rules = json.loads(subprocess.check_output(["nft", "-j", "list", "table", "inet", "polarita_test"]))["nftables"]
    zones, = [r["set"] for r in rules if r.get("set", {}).get("name") == "zones"]
    hooks = {r["chain"].get("hook") for r in rules if "chain" in r}
    if set(zones["elem"]) != set(bridges) or not {"input","forward"} <= hooks:
        raise RuntimeError("Jádro nenačetlo očekávané zóny a řetězce firewallu.")
    print("Incus", query("")["environment"]["server_version"])
    print(subprocess.check_output(["tofu", "version"], text=True).splitlines()[0])
    print("Úložiště vnitřního Incusu je na ZFS. Tři mosty, jejich profily a síťová izolace profilu sandbox_airgap odpovídají konfiguraci.")
    print(f"Prověřené kontejnery: {len(containers)}. Privilegované kontejnery: 0. Docker a jeho socket na hostiteli VM chybí.")
    print("Jádro používá tabulku nftables polarita_test se třemi zónami a vstupním i předávacím řetězcem.")


if __name__ == "__main__":
    over()
