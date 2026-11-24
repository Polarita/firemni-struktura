"""Publikování ověřeného dokumentu do místního archivu TEST. Volá jej hostitelská úloha."""
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path("/srv/polarita/data/legal-archive")
DATA = ROOT / "test"
DATASET = "polarita_zfs/data/legal-archive/test"
READER = "polarita-archiv-test"
AREAS = ("ucetnictvi-a-isdoc-10let", "mzdy-30-45let", "smlouvy-a-plne-moci", "revize-a-pasporty",
         "stavebni-deniky-10let", "datova-schranka-zfo-10let", "hovory-legal-hold-10let")


def run(*args):
    return subprocess.check_output(args, stdin=subprocess.DEVNULL, text=True).strip()


def check_host():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise RuntimeError("Archiv patří do firemní VM")
    if run("findmnt", "-no", "SOURCE", "--mountpoint", DATA) != DATASET:
        raise RuntimeError("Chybí připojený archiv TEST")
    if run("zfs", "get", "-Ho", "value", "encryptionroot", DATASET) != "polarita_zfs":
        raise RuntimeError("Archiv vyžaduje šifrovaný dataset")


def archive_dir(path):
    path.mkdir(mode=0o750, exist_ok=True)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != 0:
        raise RuntimeError("Cílový adresář nepatří správě archivu")
    gid = pwd.getpwnam(READER).pw_gid
    if path.stat().st_gid != gid:
        os.chown(path, 0, gid)
    if stat.S_IMODE(path.stat().st_mode) != 0o750:
        path.chmod(0o750)
    run("chattr", "+a", path)


def store(source, area, extension, expected_hash, year):
    check_host()
    if area not in AREAS or extension not in ("pdf", "isdoc", "zfo", "wav", "txt", "json") or not 2000 <= year <= 9999:
        raise ValueError("Neznámá agenda, rok nebo formát")
    if extension in ("txt", "json") and area != "hovory-legal-hold-10let":
        raise ValueError("Přepis a předávací údaje patří do spisového archivu hovorů")
    archive_dir(DATA / area)
    parent = DATA / area / str(year)
    archive_dir(parent)
    with TemporaryDirectory(dir=DATA / ".priprava") as tmp:
        stage = Path(tmp) / "objekt"
        stage.mkdir(mode=0o700)
        dest = stage / ("dokument." + extension)
        with os.fdopen(os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as reader:
            st = os.fstat(reader.fileno())
            if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= 128 * 1024 * 1024:
                raise RuntimeError("Neplatný vstup archivu")
            with dest.open("xb") as out:
                remaining = st.st_size
                while remaining:
                    chunk = reader.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError("Zkrácený vstup")
                    out.write(chunk)
                    remaining -= len(chunk)
                if reader.read(1):
                    raise RuntimeError("Zdroj se mění")
                out.flush()
                os.fsync(out.fileno())
        with dest.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        if digest != expected_hash:
            raise RuntimeError("Předaný kontrolní součet nesouhlasí")
        meta = {"agenda": area, "rok": year, "sha256": digest, "soubor": dest.name, "rezim": "TEST"}
        manifest = stage / "zaznam.json"
        with manifest.open("x") as stream:
            json.dump(meta, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        gid = pwd.getpwnam(READER).pw_gid
        for path in (dest, manifest):
            os.chown(path, 0, gid)
            path.chmod(0o440)
        os.chown(stage, 0, gid)
        stage.chmod(0o550)
        target = parent / digest
        with open("/run/polarita-archiv-test.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not target.exists():
                rename = ctypes.CDLL(None, use_errno=True).renameat2
                if rename(-100, os.fsencode(stage), -100, os.fsencode(target), 1):
                    raise OSError(ctypes.get_errno(), "Publikování archivu selhalo")
            final = target / dest.name
            with final.open("rb") as f:
                if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                    raise RuntimeError("Uložený dokument má jiný obsah")
            if json.loads((target / manifest.name).read_text()) != meta:
                raise RuntimeError("Nesouhlasí průvodní záznam")
            run("chattr", "+i", final, target / manifest.name)
            run("chattr", "+i", target)
            token = hashlib.sha256(str(final.relative_to(DATA)).encode()).hexdigest()
            snapshot = DATASET + "@zapis-" + token
            if subprocess.run(["zfs", "list", "-Ht", "snapshot", "-o", "name", snapshot],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                run("zfs", "snapshot", snapshot)
            if "polarita-test" not in [line.split()[1] for line in run("zfs", "holds", "-H", snapshot).splitlines()]:
                run("zfs", "hold", "polarita-test", snapshot)
            return final, snapshot
