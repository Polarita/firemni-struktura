"""Připraví pouze ověřené archivy a místní Cargo registry pro sestavení bez sítě."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tarfile
import tempfile
import time
import tomllib
from urllib.request import urlopen

REV = "7b083bca7fde98f2b97bd93a658c28c24ef55317"
SOURCE = "472777a08955c43aa6cd367fc5f1ffc7230911508a2716990d1df015472e08dd"
KUZU = "e99f9671ebfacf4d6208aa4b94490016e4ac9be242deed1fea78afb31c058ebd"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, target, expected):
    if target.is_file() and digest(target) == expected:
        return
    for attempt in range(3):
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as file:
                pending = Path(file.name)
                try:
                    with urlopen(url, timeout=45) as response:
                        shutil.copyfileobj(response, file)
                    file.flush()
                    if digest(pending) != expected:
                        raise ValueError(f"Nesouhlasí SHA-256 {target.name}")
                    os.chmod(pending, 0o644)
                    os.replace(pending, target)
                finally:
                    pending.unlink(missing_ok=True)
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def index_path(name):
    if len(name) < 3:
        return Path(str(len(name)), name)
    if len(name) == 3:
        return Path("3", name[0], name)
    return Path(name[:2], name[2:4], name)


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "aigiscode.tar.gz"
    download(f"https://codeload.github.com/Draivix/aigiscode/tar.gz/{REV}", source, SOURCE)
    download("https://github.com/kuzudb/kuzu/releases/download/v0.11.3/libkuzu-linux-x86_64.tar.gz",
             folder/"libkuzu.tar.gz", KUZU)
    download("https://raw.githubusercontent.com/kuzudb/kuzu/v0.11.3/LICENSE", folder/"LICENSE-kuzu",
             "26d1f4bc3b7e97309d1c3152e8bf00576aec900377478f2edbb51e4b3c0aca91")
    with tarfile.open(source) as archive:
        with archive.extractfile("aigiscode-"+REV+"/Cargo.lock") as manifest:
            packages = tomllib.load(manifest)["package"]
    registry = folder / "registry"
    registry.mkdir(exist_ok=True)
    required = defaultdict(dict)
    for dep in packages:
        if dep.get("source") is None and dep["name"] == "aigiscore":
            continue
        if (dep.get("source") != "registry+https://github.com/rust-lang/crates.io-index"
                or not re.fullmatch(r"[A-Za-z0-9_-]+", dep["name"])
                or not re.fullmatch(r"[A-Za-z0-9.+-]+", dep["version"])
                or not re.fullmatch(r"[a-f0-9]{64}", dep["checksum"])):
            raise ValueError("Neznámý původ nebo neplatný záznam Cargo.lock")
        required[dep["name"]][dep["version"]] = dep["checksum"]

    def crate(item):
        name, versions = item
        idx = index_path(name.lower())
        target = registry / "index" / idx
        target.parent.mkdir(parents=True, exist_ok=True)
        records = {}
        if target.is_file():
            records = {x["vers"]:x for x in map(json.loads,target.read_text().splitlines())}
        if {v:r["cksum"] for v,r in records.items()} != versions:
            for attempt in range(3):
                try:
                    with urlopen("https://index.crates.io/"+str(idx), timeout=40) as stream:
                        records = {r["vers"]:r for r in map(json.loads,stream) if r["vers"] in versions and r["name"] == name}
                    break
                except OSError:
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)
            if {v:r["cksum"] for v,r in records.items()} != versions:
                raise ValueError("Index nesouhlasí se zámkem pro "+name)
            pending = target.with_suffix(".next")
            pending.write_text("".join(json.dumps(r)+"\n" for r in records.values()))
            pending.replace(target)
        for version, sha in versions.items():
            filename = f"{name}-{version}.crate"
            download("https://static.crates.io/crates/"+name+"/"+filename, registry/filename, sha)

    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(crate, required.items()))
    print(f"Zdroj {REV}, sdílená knihovna Kuzu a {sum(map(len,required.values()))} balíků Cargo mají ověřené kontrolní součty.", flush=True)


if __name__ == "__main__":
    if socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Příprava patří do polarita-hq")
    prepare(Path(sys.argv[1]))
