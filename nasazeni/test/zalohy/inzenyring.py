"""Sběr vydaných dokladů spisů a servisních hlášení z jednoho konzistentního snímku."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory

HEX = re.compile(r"[0-9a-f]{64}")
NAMES = {"pasy":{"vyrobni-pas.pdf","prehled.json"},
         "revize":{"navrh.pdf","posouzeni.json","prehled.json"},
         "rozpocty":{"nabidka.xlsx","nabidka.xc4"}}


def otisk(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def over(root):
    root = Path(root)
    for section, expected in NAMES.items():
        for directory in (root/section).rglob("*"):
            if not HEX.fullmatch(directory.name):
                continue
            if not directory.is_dir() or directory.is_symlink():
                raise ValueError("Neplatná cesta vydání v obnoveném spisu.")
            manifest = directory/"SHA256SUMS"
            entries = manifest.read_text().splitlines()
            if (not HEX.fullmatch(directory.name) or len(entries) != len(expected) or
                    set(p.name for p in directory.iterdir()) != expected | {"SHA256SUMS"}):
                raise ValueError("Nesouhlasí obsah adresáře vydání.")
            sums = {}
            for line in entries:
                digest, name = line.split("  ",1)
                if (name not in expected or not HEX.fullmatch(digest) or (directory/name).is_symlink()
                        or digest != otisk(directory/name)):
                    raise ValueError("Nesouhlasí obnovený soubor vydání.")
                sums[name] = digest
            if set(sums) != expected or section != "rozpocty" and directory.name != otisk(manifest):
                raise ValueError("Chybné označení nebo manifest vydání.")
            if section == "revize":
                report = json.loads((directory/"prehled.json").read_bytes())
                if report["pdf_sha256"] != sums["navrh.pdf"]:
                    raise ValueError("Obnovená revize odkazuje na odlišný dokument.")
                if "vydani_pasu" in report:
                    serial, rev = report["vyrobni_cislo"], report["vydani_pasu"]
                    if not re.fullmatch(r"RZ-[0-9]{4}-[0-9]{5}",serial) or not HEX.fullmatch(rev):
                        raise ValueError("Neplatný odkaz na podklad revize.")
                    pdf = root/"pasy"/directory.parent.name/serial/rev/"vyrobni-pas.pdf"
                    if otisk(pdf) != report["pas_sha256"]:
                        raise ValueError("Nesouhlasí vydání pasu použité v revizi.")
        for link in (root/section).rglob("current"):
            if not link.is_symlink() or not HEX.fullmatch(str(link.readlink())) or not (link/"SHA256SUMS").is_file():
                raise ValueError("Chybí obnovené aktuální vydání.")
    db = root/"telemetrie.sqlite"
    if db.exists():
        with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as con:
            if con.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("Integrita obnovených hlášení OCPP nesouhlasí.")
            con.execute("SELECT stanice,zprava,spis,cas,stav FROM udalost LIMIT 1").fetchone()


def sber(rootfs, dest):
    if not (rootfs/"etc/polarita-postgres/pg_hba.conf").is_file():
        raise ValueError("Ve snímku chybí kořen databázové instance.")
    src = rootfs/"opt/polarita-inzenyring-test"
    db = rootfs/"var/lib/polarita-ocpp-test/telemetrie.sqlite"
    dest.mkdir(mode=0o700)
    for section in NAMES:
        if (src/section).is_dir():
            shutil.copytree(src/section,dest/section,symlinks=True,ignore=shutil.ignore_patterns(".*"))
    if db.is_file():
        # V okamžiku ZFS snímku mohl probíhat zápis. Případný journal obnovíme na pracovní kopii.
        with TemporaryDirectory(dir=dest) as tmp:
            work = Path(tmp)/db.name
            for suffix in ("","-journal","-wal"):
                original = db.with_name(db.name+suffix)
                if original.is_file():
                    shutil.copyfile(original, work.with_name(work.name+suffix))
            with closing(sqlite3.connect(work)) as live, closing(sqlite3.connect(dest/db.name)) as saved:
                live.backup(saved)
    over(dest)
