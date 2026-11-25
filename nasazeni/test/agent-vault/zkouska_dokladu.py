"""Přijetí, opakování a odmítnutí dávky ve skutečném dočasném znalostním Gitu."""
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

import doklady
import pamet


def vzorek(obsah):
    pack = io.BytesIO()
    with tarfile.open(fileobj=pack, mode="w") as archive:
        for i in range(8):
            data = obsah if i == 7 else f"Ověření bloku {i}\n".encode()
            item = tarfile.TarInfo(f"blok-{i:02}/prijem.txt")
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
    pack.seek(0)
    return pack


def over():
    if os.geteuid() == 0:
        raise RuntimeError("Izolovaná zkouška patří účtu znalostí.")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "vault"
        root.mkdir()
        doklady.ROOT = pamet.ROOT = root
        def git(*args):
            return pamet.git(root, *args).decode().strip()
        git("init", "-q", "-b", "main")
        git("config", "user.name", "Zkouška")
        git("config", "user.email", "znalosti@polarita.test")
        git("config", "core.hooksPath", str(pamet.HOOKS))
        (root / ".gitignore").write_text("")
        git("add", ".gitignore")
        git("commit", "-qm", "Začátek zkoušky")
        os.environ["POLARITA_VAULT_ACTOR"] = "instalace"
        data = "Ověřeno v TEST.\r\n".encode()
        good = doklady.prijmi(vzorek(data))
        if good["overene_soubory"] != 8 or good != doklady.prijmi(vzorek(data)) or git("rev-list", "--count", "HEAD") != "2":
            raise AssertionError("Opakování dávky změnilo Git.")
        try:
            doklady.prijmi(vzorek(b"heslo: synteticky-vzorek"))
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Brána nezastavila celou dávku.")
        if git("rev-parse", "HEAD") != good["revize"]:
            raise AssertionError("Odmítnutá dávka změnila větev.")
        os.environ["POLARITA_VAULT_ACTOR"] = "11001"
        try:
            doklady.prijmi(vzorek(data))
        except ValueError:
            pass
        else:
            raise AssertionError("Čtecí účet získal zápis.")
    print("Osm bloků v jednom commitu. Opakování zachovalo revizi. Brána odmítla celou vadnou dávku a čtecí účet nemohl zapisovat.")


if __name__ == "__main__":
    over()
