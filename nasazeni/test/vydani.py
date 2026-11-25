"""Ověří přílohy označeného vydání na GitHubu a uloží je do příslušné revize ve firemní VM."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

REPO = "Polarita/firemni-struktura"
DOKUMENTY = {
    "00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf", "01-ORGANIZACNI-MAPA-A3-2026.pdf",
    "04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf", "05-SOFTWAROVA-MAPA-A3-2026.pdf",
}


def otisk(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def over_soubory(directory, hashes):
    if {p.name for p in directory.iterdir()} != set(hashes):
        raise ValueError("Seznam převzatých příloh se liší od vydání na GitHubu.")
    for name, digest in hashes.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or otisk(path) != digest:
            raise ValueError(f"Nesouhlasí obsah přílohy {name}.")
    lines = (directory / "SHA256SUMS").read_text().splitlines()
    manifest = dict(line.split(maxsplit=1)[::-1] for line in lines)
    expected = {name: digest for name, digest in hashes.items() if name != "SHA256SUMS"}
    if manifest != expected or len(lines) != len(expected):
        raise ValueError("Manifest vydavatele neodpovídá jednotlivým přílohám.")


def prijmi(commit, hashes):
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise ValueError("Přílohy se instalují do VM polarita-hq.")
    directory = Path("/srv/polarita/infra/releases") / commit
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "tisk"
    with (directory / ".tisk.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.is_symlink():
            raise ValueError("Neočekávaný symbolický odkaz tiskového adresáře.")
        if target.exists():
            over_soubory(target, hashes)
            print(f"VM ověřila všech {len(hashes)} již nainstalovaných příloh v {target}.")
            return
        with tempfile.TemporaryDirectory(dir=directory, prefix=".prijem-tisku-") as tmp:
            incoming = Path(tmp) / "tisk"
            incoming.mkdir(mode=0o755)
            with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as tar:
                for item in tar:
                    if not item.isreg() or item.name not in hashes:
                        raise ValueError("Neočekávaná položka přenosu.")
                    with (incoming / item.name).open("xb") as out:
                        shutil.copyfileobj(tar.extractfile(item), out)
            over_soubory(incoming, hashes)
            incoming.rename(target)
            over_soubory(target, hashes)
    print(f"VM ověřila {len(hashes)} příloh vydání v {target}.")


def stahni(commit, directory):
    if socket.gethostname().split(".")[0] != "ejpovice":
        raise ValueError("Vydání se nasazuje z Ejpovic.")
    root = Path(__file__).resolve().parents[2]
    git = ["git", "-C", str(root)]
    canon = json.loads(subprocess.check_output([*git, "show", commit + ":nastroje/kanon.json"]))
    tag = canon["release_tag"]
    if not re.fullmatch(r"Polarita-[0-9]+(?:\.[0-9]+)+", tag) or subprocess.check_output(
            [*git, "rev-parse", "refs/tags/" + tag + "^{commit}"], text=True).strip() != commit:
        raise ValueError("Značka vydání a zdrojová revize se liší.")
    with urlopen(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}", timeout=45) as res:
        release = json.load(res)
    if release["draft"] or release["prerelease"] or release["tag_name"] != tag:
        raise ValueError("Chybí zveřejněné vydání.")
    hashes = {}
    for asset in release["assets"]:
        name = asset["name"]
        if (not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name) or name in hashes or
                not re.fullmatch(r"sha256:[0-9a-f]{64}", asset["digest"]) or
                asset["browser_download_url"] != f"https://github.com/{REPO}/releases/download/{tag}/{name}"):
            raise ValueError("Neplatná příloha vydání.")
        hashes[name] = asset["digest"][7:]
    templates = subprocess.check_output([*git, "ls-tree", "--name-only", commit + ":balicky/S1-generator-cistopisu/data"], text=True)
    forms = {Path(name).with_suffix(".pdf").name for name in templates.splitlines() if name.endswith(".json")}
    if not forms or set(hashes) != DOKUMENTY | forms | {"konfigurator.html", "manifesty-S1.zip", "SHA256SUMS"}:
        raise ValueError("Sada příloh neodpovídá dokumentům, čistopisům a konfigurátoru dané revize.")
    for asset in release["assets"]:
        path = directory / asset["name"]
        with urlopen(asset["browser_download_url"], timeout=120) as res, path.open("xb") as out:
            shutil.copyfileobj(res, out)
        if path.stat().st_size != asset["size"]:
            raise ValueError("Nesouhlasí velikost stažené přílohy.")
    over_soubory(directory, hashes)
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit")
    parser.add_argument("--prijmi", metavar="OTISKY")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise ValueError("Neplatná zdrojová revize.")
    if args.prijmi:
        hashes = json.loads(args.prijmi)
        if not isinstance(hashes, dict) or not all(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name)
                and re.fullmatch("[0-9a-f]{64}", digest) for name, digest in hashes.items()):
            raise ValueError("Neplatný seznam kontrolních součtů.")
        return prijmi(args.commit, hashes)
    with tempfile.TemporaryDirectory(prefix="polarita-vydani-") as tmp:
        directory = Path(tmp)
        hashes = stahni(args.commit, directory)
        # Přijímací část běží i před rozbalením celého zdrojového stromu ve VM.
        command = ["sudo", "-n", "incus", "exec", "-T", "--project", "polarita", "polarita-hq", "--",
                   "python3", "-c", Path(__file__).read_text(), args.commit, "--prijmi", json.dumps(hashes)]
        with tempfile.TemporaryFile() as data:
            with tarfile.open(fileobj=data, mode="w") as tar:
                for name in sorted(hashes):
                    tar.add(directory / name, arcname=name)
            data.seek(0)
            subprocess.run(command, stdin=data, check=True)
        root = Path(__file__).resolve().parents[2]
        for name in sorted(DOKUMENTY):
            with tempfile.NamedTemporaryFile(dir=root, prefix=".tisk-", delete=False) as f:
                stage = Path(f.name)
            try:
                shutil.copyfile(directory / name, stage)
                stage.chmod(0o644)
                stage.replace(root / name)
            finally:
                stage.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
