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


def mistni_vydani(directory, commit, tag, hashes=None):
    target = directory / "tisk"
    receipt = directory / "tisk-github.json"
    with (directory / ".tisk.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.is_symlink() or receipt.is_symlink():
            raise ValueError("Neočekávaný odkaz v tiskovém vydání.")
        if receipt.exists():
            stored = json.loads(receipt.read_bytes())
            if stored["commit"] != commit or stored["repo"] != REPO or (tag is not None and stored["tag"] != tag):
                raise ValueError("Potvrzení GitHubu patří k jinému vydání.")
            over_otisky(stored["sha256"])
            if hashes is not None and hashes != stored["sha256"]:
                raise ValueError("Kontrolní součty již převzatého vydání se změnily.")
            hashes = stored["sha256"]
            over_soubory(target, hashes)
            return hashes
        if hashes is None:
            return None
        over_otisky(hashes)
        with tempfile.TemporaryDirectory(dir=directory, prefix=".prijem-tisku-") as tmp:
            if not target.exists():
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
            if tag is None:
                return hashes
            stage = Path(tmp) / receipt.name
            with stage.open("x") as out:
                json.dump({"repo": REPO, "commit": commit, "tag": tag, "sha256": hashes}, out, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            stage.chmod(0o600)
            stage.replace(receipt)
        return hashes


def over_otisky(hashes):
    if (not isinstance(hashes, dict) or not (DOKUMENTY | {"SHA256SUMS"}).issubset(hashes)
            or not all(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name)
                       and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
                       for name, digest in hashes.items())):
        raise ValueError("Neplatný seznam kontrolních součtů vydání.")


def popis_revize(commit):
    if socket.gethostname().split(".")[0] != "ejpovice":
        raise ValueError("Vydání se nasazuje z Ejpovic.")
    root = Path(__file__).resolve().parents[2]
    git = ["git", "-C", str(root)]
    canon = json.loads(subprocess.check_output([*git, "show", commit + ":nastroje/kanon.json"]))
    tag = canon["release_tag"]
    if not re.fullmatch(r"Polarita-[0-9]+(?:\.[0-9]+)+", tag) or subprocess.check_output(
            [*git, "rev-parse", "refs/tags/" + tag + "^{commit}"], text=True).strip() != commit:
        raise ValueError("Značka vydání a zdrojová revize se liší.")
    templates = subprocess.check_output([*git, "ls-tree", "--name-only", commit + ":balicky/S1-generator-cistopisu/data"], text=True)
    forms = {Path(name).with_suffix(".pdf").name for name in templates.splitlines() if name.endswith(".json")}
    if not forms:
        raise ValueError("Sada příloh neodpovídá dokumentům, čistopisům a konfigurátoru dané revize.")
    return tag, DOKUMENTY | forms | {"konfigurator.html", "manifesty-S1.zip", "SHA256SUMS"}


def stahni(commit, tag, names, directory):
    with urlopen(f"https://api.github.com/repos/{REPO}/commits/{tag}", timeout=45) as res:
        if json.load(res)["sha"] != commit:
            raise ValueError("GitHub vrací pro vydaný tag odlišnou zdrojovou revizi.")
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
    if set(hashes) != names:
        raise ValueError("Seznam příloh neodpovídá zdrojové revizi.")
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prijmi", metavar="OTISKY")
    mode.add_argument("--over-ulozene", action="store_true")
    parser.add_argument("--tag")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise ValueError("Neplatná zdrojová revize.")
    if args.prijmi is not None or args.over_ulozene:
        if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
            raise ValueError("Přílohy se ověřují uvnitř VM polarita-hq.")
        if ((args.over_ulozene and args.tag is None) or
                (args.tag is not None and not re.fullmatch(r"Polarita-[0-9]+(?:\.[0-9]+)+", args.tag))):
            raise ValueError("Chybí přesný tag přijímaného vydání.")
        base = Path("/srv/polarita/infra/releases") / args.commit
        base.mkdir(parents=True, exist_ok=True)
        hashes = json.loads(args.prijmi) if args.prijmi is not None else None
        if args.prijmi is not None:
            over_otisky(hashes)
        result = mistni_vydani(base, args.commit, args.tag, hashes)
        print(json.dumps(result) if args.over_ulozene else f"VM převzala a ověřila {len(result)} příloh.")
        return

    tag, names = popis_revize(args.commit)
    incus = ["sudo", "-n", "incus"]
    command = [*incus, "exec", "-T", "--project", "polarita", "polarita-hq", "--",
               "python3", "-c", Path(__file__).read_text(), args.commit, "--tag", tag]
    hashes = json.loads(subprocess.check_output([*command, "--over-ulozene"]))
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix=".tisk-", dir=root) as tmp:
        directory = Path(tmp)
        if hashes is None:
            hashes = stahni(args.commit, tag, names, directory)
            with tempfile.TemporaryFile() as data:
                with tarfile.open(fileobj=data, mode="w") as tar:
                    for name in sorted(hashes):
                        tar.add(directory / name, arcname=name)
                data.seek(0)
                subprocess.run([*command, "--prijmi", json.dumps(hashes)], stdin=data, check=True)
        else:
            if set(hashes) != names:
                raise ValueError("Potvrzení vydání neobsahuje přesnou sadu příloh této revize.")
            print(f"VM znovu ověřila {len(hashes)} příloh {tag} podle uloženého potvrzení GitHubu.")
        for name in sorted(DOKUMENTY):
            target = root / name
            if not target.is_symlink() and target.is_file() and otisk(target) == hashes[name]:
                continue
            stage = directory / name
            if not stage.exists():
                remote = f"polarita-hq/srv/polarita/infra/releases/{args.commit}/tisk/{name}"
                with stage.open("xb") as out:
                    subprocess.run([*incus, "file", "pull", "--project", "polarita", remote, "-"], stdout=out, check=True)
            if otisk(stage) != hashes[name]:
                raise ValueError(f"Nesouhlasí vydaný dokument {name}.")
            stage.chmod(0o644)
            stage.replace(target)


if __name__ == "__main__":
    main()
