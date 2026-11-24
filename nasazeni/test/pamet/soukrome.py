"""Oddělí soukromý bootstrap od verzovaných znalostí. Starší vydání mají kompatibilní cesty."""
import ctypes
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

VAULT = Path("/srv/polarita/vault")
PRIVATE = Path("/srv/polarita/data/bootstrap-test")
AREAS = ("test-login", "openbao-test", "keycloak-test")
SNAP = "pred-oddelenim-test"


def run(*args):
    return subprocess.run(args, input=b"", capture_output=True, check=True).stdout.decode().strip()


def inventory(path):
    found = {}
    for item in [path, *sorted(path.rglob("*"))]:
        st = item.lstat()
        if item.is_symlink() or not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
            raise RuntimeError("Neočekávaný typ souboru při přesunu bootstrapu")
        value = None
        if item.is_file():
            with item.open("rb") as f:
                value = hashlib.file_digest(f, "sha256").digest()
        found[item.relative_to(path)] = (st.st_mode, st.st_uid, st.st_gid, value)
    return found


def exchange(a, b):
    fn = ctypes.CDLL(None, use_errno=True).renameat2
    if fn(-100, os.fsencode(a), -100, os.fsencode(b), 2) != 0:
        raise OSError(ctypes.get_errno(), "Atomická výměna cesty se nezdařila")


def main():
    if run("hostname", "-s") != "polarita-hq" or os.geteuid() != 0:
        sys.exit("Přesun patří do firemní VM")
    os.umask(0o077)
    if run("findmnt", "-no", "SOURCE", "--mountpoint", VAULT) != "polarita_zfs/vault":
        raise RuntimeError("Chybí původní dataset")
    dataset = "polarita_zfs/data/bootstrap-test"
    with Path("/run/polarita-bootstrap-migrace.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if dataset not in run("zfs", "list", "-Ho", "name").splitlines():
            if PRIVATE.exists() and any(PRIVATE.iterdir()):
                raise RuntimeError("Cílové umístění obsahuje jiná data")
            run("zfs", "create", "-o", "mountpoint=" + str(PRIVATE), "-o", "compression=lz4", dataset)
        if run("zfs", "get", "-Ho", "value", "mounted", dataset) == "no":
            run("zfs", "mount", dataset)
        if run("findmnt", "-no", "SOURCE", "--mountpoint", PRIVATE) != dataset or run(
                "zfs", "get", "-Ho", "value", "encryptionroot", dataset) != "polarita_zfs":
            raise RuntimeError("Chybné šifrování nebo připojení cílového úložiště")
        PRIVATE.chmod(0o700)
        snap = "polarita_zfs/vault@" + SNAP
        if any((VAULT / n).is_dir() and not (VAULT / n).is_symlink() for n in AREAS):
            if snap not in run("zfs", "list", "-Ht", "snapshot", "-o", "name", "-r", "polarita_zfs/vault").splitlines():
                run("zfs", "snapshot", snap)
        for name in AREAS:
            source, target = VAULT / name, PRIVATE / name
            shadow = VAULT / (".migrace-" + name)
            if not source.is_symlink():
                if source.is_dir():
                    saved = VAULT / ".zfs/snapshot" / SNAP / name
                    original = inventory(source)
                    if inventory(saved) != original:
                        raise RuntimeError("Bootstrap se od snímku změnil. Původní cesta zůstala aktivní.")
                    if not target.exists():
                        stage = PRIVATE / (".kopie-" + name)
                        stage.mkdir(mode=0o700, exist_ok=True)
                        run("cp", "-a", str(source) + "/.", stage)
                        if inventory(stage) != original:
                            raise RuntimeError("Kontrola pracovní kopie neprošla")
                        stage.rename(target)
                    if inventory(target) != original:
                        raise RuntimeError("Cílová kopie se liší. Původní cesta zůstala aktivní.")
                    if not shadow.is_symlink():
                        shadow.symlink_to(target)
                    if shadow.readlink() != target:
                        raise RuntimeError("Cizí přechodový odkaz")
                    exchange(source, shadow)
                else:
                    target.mkdir(mode=0o700, exist_ok=True)
                    source.symlink_to(target)
            if source.readlink() != target or not target.is_dir():
                raise RuntimeError("Nesouhlasí kompatibilní cesta")
            if shadow.exists():
                # Tato přesná stará kopie zůstává celá v neměnném snímku i v novém datasetu.
                if shadow.is_symlink() or inventory(shadow) != inventory(VAULT / ".zfs/snapshot" / SNAP / name):
                    raise RuntimeError("Přechodová kopie se liší od snímku")
                shutil.rmtree(shadow)
        src = Path(__file__).resolve().parent
        run("install", "-D", "-m", "0755", src/"pripoj.sh", "/usr/local/lib/polarita/pripoj-bootstrap")
        run("install", "-m", "0644", src/"polarita-bootstrap.service", "/etc/systemd/system/")
        incus_unit = Path("/etc/systemd/system/incus.service.d")
        incus_unit.mkdir(parents=True, exist_ok=True, mode=0o755)
        dropin = incus_unit / "polarita-bootstrap.conf"
        dropin.write_text("[Unit]\nRequires=polarita-bootstrap.service\nAfter=polarita-bootstrap.service\n")
        dropin.chmod(0o644)
        run("systemctl", "daemon-reload")
        run("systemctl", "enable", "--now", "polarita-bootstrap.service")
        print("Soukromý bootstrap používá samostatný šifrovaný dataset. Původní tři cesty vedou do stejného soukromého úložiště.")


if __name__ == "__main__":
    main()
