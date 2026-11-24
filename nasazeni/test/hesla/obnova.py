"""Pořídí konzistentní kopii šifrovaného datasetu a přihlásí klienta do obnoveného Vaultwardenu."""
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time

from pozvanka import run

DATA = Path("/srv/polarita/data/vaultwarden")
DATASET = "polarita_zfs/data/vaultwarden"
BACKUP = Path("/srv/polarita/backups/vaultwarden")


def verify():
    if run("findmnt", "-n", "-o", "SOURCE", "--mountpoint", str(DATA)).decode().strip() != DATASET:
        raise RuntimeError("Nesouhlasí datový svazek")
    name = "obnova-hesla-" + secrets.token_hex(5)
    with ExitStack() as cleanup:
        tmp = Path(cleanup.enter_context(tempfile.TemporaryDirectory(dir=BACKUP)))
        archive = tmp / "data.tar.gz"
        snapshot = DATASET + "@" + name
        run("zfs", "snapshot", snapshot)
        try:
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(DATA / ".zfs" / "snapshot" / name / "test", arcname="data")
        finally:
            run("zfs", "destroy", snapshot)
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar:
                if not (member.isfile() or member.isdir()):
                    raise RuntimeError("Neočekávaný typ souboru v záloze")
            tar.extractall(tmp, filter="data")
        with sqlite3.connect((tmp / "data/db.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("pragma integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("Kontrola konzistence obnovené SQLite selhala")
        run("incus", "init", "local:polarita-vaultwarden-test-1.37.5", name, "-p", "default", "-p", "sandbox_airgap",
            "-c", "limits.memory=256MiB", "-c", "limits.memory.swap=false",
            "-c", "environment.DOMAIN=https://obnova.polarita.test/hesla", "-c", "environment.SIGNUPS_ALLOWED=false",
            "-c", "environment.INVITATIONS_ALLOWED=false", "-c", "environment.ROCKET_PORT=8080",
            "-c", "environment.ROCKET_ADDRESS=127.0.0.1", "-c", "environment.DISABLE_ICON_DOWNLOAD=true")
        cleanup.callback(run, "incus", "delete", "--force", name)
        run("incus", "config", "device", "add", name, "hesla", "disk", "source=" + str(tmp / "data"),
            "path=/data", "shift=true")
        run("incus", "start", name)
        state = json.loads(run("incus", "query", "/1.0/instances/" + name + "/state"))
        ns = ["nsenter", "--net=/proc/" + str(state["pid"]) + "/ns/net", "--"]
        if [link["ifname"] for link in json.loads(run(*ns, "ip", "-j", "link"))] != ["lo"]:
            raise RuntimeError("Kopie má síťovou kartu")
        run(*ns, "ip", "link", "set", "lo", "up")
        for _ in range(45):
            if subprocess.run(ns + ["curl", "-fs", "-o", "/dev/null", "http://127.0.0.1:8080/hesla/alive"]).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Obnovená instance neodpovídá")
        # Jen čtení. Prázdná záloha nesmí projít vytvořením nových kolekcí.
        subprocess.run(ns + [sys.executable, str(Path(__file__).with_name("ucet.py")), "--klient", "--jen-cteni"], check=True)
        archive.replace(BACKUP / "posledni.tar.gz")
    print("Záloha Vaultwarden prošla kontrolou SQLite i přihlášením a čtením osmi kolekcí v kopii bez sítě.")


if __name__ == "__main__":
    if run("hostname", "-s").strip() != b"polarita-hq":
        sys.exit("Obnova patří do firemní VM")
    os.umask(0o077)
    BACKUP.mkdir(parents=True, exist_ok=True)
    with (BACKUP / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        verify()
