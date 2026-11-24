"""Přečte obnovenou konfiguraci a úložiště v offline instanci. Žádná získaná identita se nevypisuje."""
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tarfile
import tempfile


def verify(root):
    target=root/"infrastruktura"
    for name in ("postgres-test","keycloak-test","stalwart-mx-test","caddy-test","headscale-test"):
        if name not in {x["name"] for x in json.loads((target/"incus/instance.json").read_bytes())}:
            raise RuntimeError("V inventáři zálohy chybí služba "+name)
    profiles={x["name"] for x in json.loads((target/"incus/profile.json").read_bytes())}
    if not {"default","app_internal","data_vault","dmz_edge","sandbox_airgap"}.issubset(profiles):
        raise RuntimeError("V záloze chybí některá síťová zóna Incusu")
    for name in ("incus","hrana","mx-test","keycloak-test/tofu"):
        state=json.loads((target/"opentofu"/name/"terraform.tfstate").read_bytes())
        if not state.get("lineage") or not state.get("resources"):
            raise RuntimeError("Neúplný obnovený stav OpenTofu")
    if b"vpn.polarita.test" not in (target/"hrana/conf/Caddyfile").read_bytes():
        raise RuntimeError("Chybí interní vhost Caddy")
    with tempfile.TemporaryDirectory() as tmp:
        local=Path(tmp)
        with tarfile.open(target/"headscale.tar") as bundle, bundle.extractfile("volume.tar") as volume:
            with tarfile.open(fileobj=volume) as hs:
                for entry in ("noise.key","derp.key"):
                    if hs.getmember("backup/volume/"+entry).size==0:
                        raise RuntimeError("Chybí identita serveru Headscale")
                for entry in ("db.sqlite","db.sqlite-wal","db.sqlite-shm"):
                    name="backup/volume/"+entry
                    if name in hs.getnames():
                        with hs.extractfile(name) as source,(local/entry).open("xb") as out:
                            shutil.copyfileobj(source,out)
        with sqlite3.connect((local/"db.sqlite").as_uri()+"?mode=ro",uri=True) as db:
            if db.execute("pragma integrity_check").fetchone()!=("ok",):
                raise RuntimeError("Obnovená databáze Headscale je poškozená")
            for table in ("users","nodes","pre_auth_keys"):
                db.execute("select count(*) from "+table).fetchone()
    with tarfile.open(target/"stalwart-mx.tar") as mx:
        base="backup/volume/rocksdb/"
        manifest=mx.extractfile(base+"CURRENT").read().decode().strip()
        if not re.fullmatch(r"MANIFEST-\d+",manifest) or mx.getmember(base+manifest).size==0:
            raise RuntimeError("Chybí aktivní manifest příchozí pošty RocksDB")
        if not any(name.startswith(base) and name.endswith(".sst") for name in mx.getnames()):
            raise RuntimeError("V obnoveném RocksDB chybí tabulky úložiště")
    print("Obnovené stavy OpenTofu a inventář Incusu obsahují firemní služby. SQLite Headscale prošla kontrolou integrity, RocksDB MX má manifest a tabulky.")
