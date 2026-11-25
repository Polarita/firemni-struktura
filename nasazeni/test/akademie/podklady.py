"""Před instalací Akademie stáhne a podle zámku ověří vstupy ve firemní VM."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from tempfile import NamedTemporaryFile

CACHE = Path("/srv/polarita/infra/akademie-test/distribuce")
LOCK = Path(__file__).with_name("distribuce.lock.json")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(cache, packages):
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / ".stazeni.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for name, package in packages.items():
            target = cache / name
            expected = package["sha256"]
            if not target.is_file() or digest(target) != expected:
                with NamedTemporaryFile(dir=cache, prefix=".stazeni-", delete=False) as stream:
                    tmp = Path(stream.name)
                try:
                    subprocess.run(["curl", "--proto", "=https", "--proto-redir", "=https",
                                    "--fail", "--location", "--silent", "--show-error",
                                    "--retry", "3", "--connect-timeout", "15", "--max-time", "600",
                                    "--output", str(tmp), package["url"]], check=True)
                    if digest(tmp) != expected:
                        raise ValueError(f"Kontrolní součet distribuce nesouhlasí: {name}")
                    tmp.chmod(0o644)
                    tmp.replace(target)
                finally:
                    tmp.unlink(missing_ok=True)
            print(f"SHA-256 ověřen: {name} {expected}", flush=True)


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Podklady Akademie patří do polarita-hq.")
    prepare(CACHE, json.loads(LOCK.read_text()))
