"""Zpřístupní offline resolveru TypeScriptu přesnou konfiguraci Astro z npm lockfilu."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tarfile
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

RUNNER = "gitea-runner-test"
CACHE = Path("/srv/polarita/infra/gitea-runner-test/podklady/astro")
LOCK = Path(__file__).resolve().parents[1] / "web/package-lock.json"


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Příprava CI patří do firemní VM.")
    package = json.loads(LOCK.read_text())["packages"]["node_modules/astro"]
    version = package["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Neplatná verze Astro")
    url = f"https://registry.npmjs.org/astro/-/astro-{version}.tgz"
    if package["resolved"] != url:
        raise ValueError("Neznámý zdroj Astro")
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / f"astro-{version}.tgz"
    def matches(path):
        with path.open("rb") as f:
            sha = hashlib.file_digest(f, "sha512").digest()
        return "sha512-" + base64.b64encode(sha).decode() == package["integrity"]
    if not archive.is_file() or not matches(archive):
        with urlopen(url, timeout=60) as response, NamedTemporaryFile(dir=CACHE, delete=False) as out:
            path = Path(out.name)
            try:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
                out.flush()
                if not matches(path):
                    raise ValueError("Nesouhlasí SHA-512 balíčku Astro")
                path.replace(archive)
            finally:
                path.unlink(missing_ok=True)
    inc = ["incus", "exec", "-T", RUNNER, "--"]
    dest = "/opt/polarita-astro-config/" + version
    subprocess.run(inc + ["install", "-dm0755", dest + "/tsconfigs", "/node_modules"], check=True)
    with tarfile.open(archive) as t:
        for name in ("tsconfigs/base.json", "tsconfigs/strict.json", "LICENSE"):
            data = t.extractfile("package/" + name).read()
            subprocess.run(inc + ["sh", "-ec", 'tmp=$(mktemp "$1.XXXXXXXX"); cat >"$tmp"; chmod 644 "$tmp"; mv -T "$tmp" "$1"', "--", dest + "/" + name],
                           input=data, check=True)
    subprocess.run(inc + ["sh", "-ec", '''
        cd /node_modules
        if test -e astro || test -L astro; then
            case $(readlink astro) in /opt/polarita-astro-config/*) ;; *) exit 1 ;; esac
        fi
        ln -sfn "$1" .polarita-astro-next
        mv -Tf .polarita-astro-next astro
        runuser -u pol-ci -- test -r /node_modules/astro/tsconfigs/base.json
        ''', "--", dest], check=True)
    print(f"Runner má mimo pracovní stromy původní pravidla TypeScriptu z Astro {version}.")


if __name__ == "__main__":
    main()
