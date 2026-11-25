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


def download(url, filename, integrity):
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / filename
    def matches(path):
        with path.open("rb") as f:
            sha = hashlib.file_digest(f, "sha512").digest()
        return "sha512-" + base64.b64encode(sha).decode() == integrity
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
    return archive


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
    archive = download(url, f"astro-{version}.tgz", package["integrity"])
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
    packages = json.loads(LOCK.read_text())["packages"]
    binding = packages["node_modules/@astrojs/compiler-binding-linux-x64-gnu"]
    binding_version = binding["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", binding_version):
        raise ValueError("Neplatná verze kompilátoru Astro")
    url = "https://registry.npmjs.org/@astrojs/compiler-binding-linux-x64-gnu/-/compiler-binding-linux-x64-gnu-" + binding_version + ".tgz"
    if binding["resolved"] != url:
        raise ValueError("Neznámý zdroj kompilátoru Astro")
    archive = download(url, "compiler-" + binding_version + ".tgz", binding["integrity"])
    root = "/opt/polarita-astro-ci"
    subprocess.run(inc + ["install", "-dm0755", root], check=True)
    subprocess.run(["bash", str(LOCK.parent.parent / "medusa/node.sh")], check=True)
    node = Path("/srv/polarita/infra/medusa-test/distribuce/node-v26.13.1-linux-x64")
    def install(source, target, mode):
        with source.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        remote = root + "/" + target
        current = subprocess.run(inc + ["sha256sum", remote], capture_output=True, text=True)
        if current.returncode == 0 and current.stdout.split()[0] == digest:
            return
        subprocess.run(["incus", "file", "push", "--mode=" + mode, str(source), RUNNER + remote + ".next"], check=True)
        subprocess.run(inc + ["mv", "-T", remote + ".next", remote], check=True)
    with tarfile.open(archive) as t, NamedTemporaryFile(dir=CACHE) as out:
        with t.extractfile("package/astro.linux-x64-gnu.node") as src:
            while chunk := src.read(1024 * 1024):
                out.write(chunk)
        out.flush()
        install(Path(out.name), "compiler.node", "0644")
    install(node / "bin/node", "node", "0755")
    install(node / "LICENSE", "LICENSE-node", "0644")
    install(Path(__file__).with_name("aigis") / "astro.cjs", "astro.cjs", "0644")
    print(f"Runner má mimo pracovní stromy původní pravidla TypeScriptu z Astro {version}.")


if __name__ == "__main__":
    main()
