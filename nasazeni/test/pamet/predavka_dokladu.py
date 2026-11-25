"""Vystaví čitelný protokol po kontrole obsahu přijaté revize proti soukromému indexu."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys


def potvrzeni(report):
    proof = report["predani"]
    rev = proof["revize"]
    root = Path(report["pracovni_kopie"])
    if (not re.fullmatch(r"[0-9a-f]{40}", rev)
            or root.parent != Path("/srv/polarita/data/bootstrap-test/prejimky-dukazu")
            or not re.fullmatch("[0-9a-f]{64}", root.name)):
        raise ValueError("Nesouhlasí identita přejímky.")
    index = (root/"index.json").read_bytes()
    records = json.loads(index)
    if hashlib.sha256(index).hexdigest() != root.name:
        raise ValueError("Nesouhlasí otisk soukromého indexu.")
    counts = Counter(r["cesta"].split("/", 1)[0] for r in records)
    if sorted(counts) != [f"blok-{i:02}" for i in range(8)] or len(records) != proof["overene_soubory"]:
        raise ValueError("Nesouhlasí soupis přijatých dokladů.")
    git = ["git","-c","safe.directory=/srv/polarita/vault","-C","/srv/polarita/vault"]
    paths = [f"{rev}:07-IT-a-Architektura/{r['cesta']}" for r in records]
    data = subprocess.run([*git, "cat-file", "--batch"], input=("\n".join(paths)+"\n").encode(),
                          stdout=subprocess.PIPE, check=True)
    stream = io.BytesIO(data.stdout)
    for rec in records:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError("Ve znalostním Gitu chybí verzovaný doklad.")
        current = hashlib.sha256(stream.read(int(header[2]))).hexdigest()
        if current != rec["cil_sha256"] or stream.read(1) != b"\n":
            raise ValueError("Obsah znalostního Gitu nesouhlasí s přejímkou.")
    print(f"Znalostní Git uchovává {len(records)} dokladů z osmi bloků. Revize {rev}.")
    print("Počet dokladů podle bloku")
    for block in sorted(counts):
        print(f"{block}  {counts[block]}")
    same = sum(r["zdroj_sha256"] == r["cil_sha256"] for r in records)
    print(f"Beze změny obsahu {same}. Převedené technické doklady {len(records)-same}.")
    print("Každý uložený soubor byl znovu načten a ověřen vůči SHA-256 přijaté kopie. Originály obsahuje snímek ZFS pro čtení.")


if __name__ == "__main__":
    potvrzeni(json.load(sys.stdin))
