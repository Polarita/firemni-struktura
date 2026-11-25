"""Jedna verzovaná předávka technických dokladů 0–7 ve znalostním Gitu."""
import hashlib
import io
import os
from pathlib import PurePosixPath
import re
import subprocess
import tarfile

from pamet import ROOT, save, snapshot

OBLAST = "07-IT-a-Architektura"
ZPRAVA = "Přejímka technických dokladů bloků 0–7"


def prijmi(stream):
    if os.environ.get("POLARITA_VAULT_ACTOR") != "instalace":
        raise ValueError("Hromadnou přejímku provádí instalační účet.")
    files = {}
    blocks = set()
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for entry in archive:
            path = PurePosixPath(entry.name)
            if (not entry.isfile() or path.as_posix() != entry.name or len(path.parts) < 2
                    or not re.fullmatch("blok-0[0-7]", path.parts[0])
                    or any(part.startswith(".") or "\n" in part or "\r" in part for part in path.parts)):
                raise ValueError("Neočekávaná cesta nebo typ předávaného dokladu.")
            name = f"{OBLAST}/{path}"
            if name in files:
                raise ValueError("Opakovaný soubor v přejímce.")
            files[name] = archive.extractfile(entry).read()
            blocks.add(path.parts[0])
    if len(blocks) != 8:
        raise ValueError("Přejímka postrádá důkazy některého z bloků 0–7.")
    rev = save(files, ZPRAVA, doklady=True)
    _, entries = snapshot(doklady=True, head=rev)
    ids = [entries[name] for name in files]
    batch = subprocess.run(["git", "-c", f"safe.directory={ROOT}", "-C", ROOT, "cat-file", "--batch"],
                           input=("\n".join(ids)+"\n").encode(), stdout=subprocess.PIPE, check=True)
    objects = io.BytesIO(batch.stdout)
    for oid, data in zip(ids, files.values()):
        header = objects.readline().decode().split()
        if header != [oid, "blob", str(len(data))]:
            raise RuntimeError("Git nevrátil požadovaný doklad.")
        if (hashlib.sha256(objects.read(len(data))).digest() != hashlib.sha256(data).digest()
                or objects.read(1) != b"\n"):
            raise RuntimeError("Uložený obsah nesouhlasí se zdrojovým SHA-256.")
    if objects.read(1):
        raise RuntimeError("Git vrátil dodatečný obsah.")
    return {"revize": rev, "bloky": len(blocks), "overene_soubory": len(files)}
