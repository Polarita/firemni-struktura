"""Přesuň pouze ověřené veřejné balíky z datového poolu do cache na systémovém disku VM."""
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import socket
import stat
from tempfile import NamedTemporaryFile, TemporaryDirectory

INFRA = Path("/srv/polarita/infra")
CACHE = Path("/var/cache/polarita-distribuce")
BALIKY = {
    "karantena-test/priprava/dangerzone-full_0.11.1_amd64.deb": "0ae0a0db9befc71afcff1af0c65400d61af8f923c6100c4c77d5866b11da80da",
    "checkmk-test/zdroje/check-mk-community-2.5.0p21_0.resolute_amd64.deb": "1c0b8dc37dc6afe69b9165b657e141e5b37381e6fb2f84f95a8c638654b58309",
    "gitea-runner-test/podklady/chromium-159.0.8154.6.zip": "77a6442fd3c8acd3bef9e1067fc26f5ef464277d22f0e8cb58dc3e4077a3e458",
    "zulip-test/zdroje/zulip-server-13.3.tar.gz": "9fb82bab771ec4690590014b8416197ba3d25fa74a09fd57d555ef0713229d36",
    "crowdsec-test/balicky/crowdsec-release.tgz": "6e0b2add0ff3231dca3db7146834d7fea028215b915e2da39ebe30fc9f11436f",
}


def over(path, expected):
    with path.open("rb") as file:
        if hashlib.file_digest(file, "sha256").hexdigest() != expected:
            raise ValueError(f"Nesouhlasí SHA-256: {path.name}")


def syncdir(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def uloz(source, cache, expected):
    target = cache / source.name
    if source.is_symlink():
        if source.readlink() != target or target.is_symlink():
            raise ValueError(f"Cizí odkaz {source}")
        over(target, expected)
        return 0
    if not source.exists():
        return 0
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"Neočekávaný typ souboru {source}")
    if target.is_symlink():
        raise ValueError(f"Cizí odkaz {target}")
    if target.exists():
        over(target, expected)
        over(source, expected)
    else:
        with NamedTemporaryFile(dir=cache, delete_on_close=False) as tmp:
            with source.open("rb") as file:
                shutil.copyfileobj(file, tmp, 1024 * 1024)
            tmp.flush()
            os.fchmod(tmp.fileno(), 0o644)
            os.fsync(tmp.fileno())
            over(Path(tmp.name), expected)
            os.link(tmp.name, target)
        syncdir(cache)
    with TemporaryDirectory(dir=source.parent) as tmp:
        link = Path(tmp) / "balik"
        link.symlink_to(target)
        now = source.lstat()
        if (now.st_ino, now.st_ctime_ns) != (before.st_ino, before.st_ctime_ns):
            raise RuntimeError(f"Zdroj se změnil: {source}")
        link.replace(source)
        syncdir(source.parent)
    return before.st_size


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Cache se připravuje pouze v polarita-hq.")
    CACHE.mkdir(mode=0o755, exist_ok=True)
    info = CACHE.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid or info.st_mode & 0o022 or info.st_dev == INFRA.stat().st_dev:
        raise SystemExit("Cache musí být na samostatném disku pod správou root.")
    with (CACHE / ".priprava").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for name, digest in BALIKY.items():
            size = uloz(INFRA / name, CACHE, digest)
            if size:
                print(f"{name}: {size} bajtů uloženo s ověřeným SHA-256", flush=True)


if __name__ == "__main__":
    main()
