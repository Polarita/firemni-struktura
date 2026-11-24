"""Kontrola obnovených dat výhradně v dočasném kontejneru bez sítě."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess

if not re.fullmatch("restic-obnova-[a-f0-9]{12}",socket.gethostname().split(".")[0]) or os.listdir("/sys/class/net")!=["lo"]:
    raise SystemExit("Zkouška vyžaduje dočasnou izolovanou instanci")
root=Path("/var/tmp/obnova-polarita")
sums=json.loads((root/"soubory.sha256.json").read_bytes())
actual_paths={str(f.relative_to(root)) for f in root.rglob("*") if not f.is_symlink() and f.is_file()}
if actual_paths!=set(sums)|{"soubory.sha256.json"}:
    raise RuntimeError("Seznam souborů ze zálohy se liší")
for name,expected in sums.items():
    with (root/name).open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!=expected:
            raise RuntimeError("Neodpovídá kontrolní součet obnoveného souboru")
for path in [root/"znalosti",*sorted((root/"gitea").glob("*/*.git"))]:
    subprocess.run(["git","-c","safe.directory="+str(path),"-C",str(path),"fsck","--full","--strict"],check=True,stdout=subprocess.DEVNULL)
if not (root/"gitea/spravce/firemni-struktura-test.git/HEAD").is_file():
    raise RuntimeError("Chybí repozitář správce")
db=root/"vaultwarden/db.sqlite3"
with sqlite3.connect(db.as_uri()+"?mode=ro",uri=True) as con:
    if con.execute("pragma integrity_check").fetchone()!=("ok",) or con.execute("select count(*) from collections").fetchone()[0]!=8:
        raise RuntimeError("Obnovený trezor hesel nepotvrdil integritu a testovací kolekce")
archive=root/"legal-archive"
for receipt in archive.glob("*/*/*/zaznam.json"):
    record=json.loads(receipt.read_bytes())
    if sums[str((receipt.parent/record["soubor"]).relative_to(root))]!=record["sha256"]:
        raise RuntimeError("Výsledek obnovy se liší od průvodního záznamu archivu")
for record in (archive/"hovory-legal-hold-10let").glob("*/*/dokument.json"):
    detail=json.loads(record.read_bytes())
    for item in detail["casti"].values():
        dest=record.parent.parent/item["sha256"]/("dokument."+item["format"])
        if sums.get(str(dest.relative_to(root)))!=item["sha256"]:
            raise RuntimeError("V obnoveném spisu chybí nahrávka nebo přepis")
if not list(archive.glob("stavebni-deniky-10let/*/*/dokument.pdf")):
    raise RuntimeError("Chybí zapečetěný list deníku")
buckets=list((root/"garage").iterdir())
if len(buckets)!=7 or any(d.name=="hovory" for d in buckets):
    raise RuntimeError("Neplatné oddělení provozních nahrávek od dlouhodobé zálohy")
objects=0
for bucket in buckets:
    for item in json.loads((bucket/"seznam.json").read_bytes()):
        if item["soubor"]!=hashlib.sha256(item["klic"].encode()).hexdigest() or not (bucket/item["soubor"]).is_file():
            raise RuntimeError("Nelze obnovit objekt podle původního klíče Garage")
        objects+=1
sample=(root/"garage/foto-staveb"/hashlib.sha256(b"zkouska/obnova-zalohy-test-v1.pgm").hexdigest())
if sample.read_bytes()!=b"P2\n2 2\n255\n0 85\n170 255\n":
    raise RuntimeError("Zdrojový kontrolní objekt Garage se liší po obnově")
if (root/"infrastruktura").is_dir():
    from over_infrastrukturu import verify
    verify(root)
print(f"Bez síťové karty ověřeno {len(sums)} souborů, integrita Git a Vaultwarden, archivní hashe a {objects} objektů v sedmi účelových koších.")
