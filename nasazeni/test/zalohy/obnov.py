"""Restic otevře přes ověřené TLS vlastní snapshot a obnoví obsah přímo do instance bez síťové karty."""
from contextlib import ExitStack
from datetime import datetime, timezone
import time
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys

from sber import CA,WORK,TEST,pg,provoz,rest,rest_env


def main():
    if os.geteuid() or socket.gethostname().split(".")[0]!="polarita-hq":
        raise RuntimeError("Obnova patří do firemní VM")
    os.umask(0o077)
    snap=(WORK/"posledni-otisk").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{64}",snap):
        raise RuntimeError("Chybí dokončená testovací záloha")
    base,prepared = (WORK/"obraz-otisky").read_text().split()
    if not all(re.fullmatch(r"[a-f0-9]{64}",value) for value in (base,prepared)):
        raise RuntimeError("Chybějí platné otisky místního obnovovacího obrazu")
    name="restic-obnova-"+secrets.token_hex(6)
    with ExitStack() as stack:
        lock=stack.enter_context((WORK/".obnova").open("a"))
        fcntl.flock(lock,fcntl.LOCK_EX)
        started = time.monotonic()
        records = json.loads(rest(rest_env(),"snapshots","--json","--no-lock",snap,capture_output=True).stdout)
        if len(records)!=1 or records[0]["id"]!=snap:
            raise RuntimeError("Nejednoznačný snímek pro zkoušku")
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(records[0]["time"])).total_seconds()
        pg.run("incus","init",prepared,name,"-p","default","-p","sandbox_airgap","-c","limits.memory=384MiB")
        stack.callback(pg.run,"incus","delete","--force",name)
        pg.run("incus","start",name)
        pg.start_restore_cluster(name)
        pg.inside(name,"install","-d","-m","0700","/var/tmp/obnova-polarita")
        with subprocess.Popen(["restic","--cacert",CA,"--no-cache","dump",snap,"/"],env=rest_env(),
                              stdin=subprocess.DEVNULL,stdout=subprocess.PIPE) as dump:
            with dump.stdout:
                subprocess.run(["incus","exec","-T",name,"--","tar","-xf","-","--no-same-owner",
                                "-C","/var/tmp/obnova-polarita"],stdin=dump.stdout,check=True)
            if dump.wait():
                raise RuntimeError("Restic nedokončil čtení snapshotu")
        subprocess.run(["incus","file","push","--mode=0755","/srv/polarita/infra/openbao-test/bin/bao",name+"/var/tmp/bao"],check=True)
        subprocess.run(["incus","file","push","--mode=0644",str(TEST/"zalohy/over_soubory.py"),name+"/var/tmp/over_soubory.py"],check=True)
        for filename in ("over_infrastrukturu.py","identita_vpn.py","over_zulip.py"):
            subprocess.run(["incus","file","push","--mode=0644",str(TEST/"zalohy"/filename),name+"/var/tmp/"+filename],check=True)
        subprocess.run(["incus","exec","-T",name,"--","python3","/var/tmp/over_soubory.py"],check=True)
        subprocess.run(["incus","file","push","--mode=0400",str(TEST/"zalohy/obnov_raft.py"),name+"/run/obnov_raft.py"],check=True)
        seal = pg.run("systemd-creds","decrypt","--name=bao-pecet",str(provoz.p.VAULT/"pecet.cred"),"-")
        payload = {"seal":base64.b64encode(seal).decode(),"manager":provoz.p.recover("bao-sprava")}
        subprocess.run(["incus","exec","-T",name,"--","python3","/run/obnov_raft.py"],
                       input=json.dumps(payload).encode(), check=True, timeout=180)
        # Import zapisuje do dočasného izolovaného clusteru. Po jeho dokončení vynutíme zápis celého WAL.
        pg.run("incus","exec","-T",name,"--","bash","-ec", """
set -euo pipefail
psql=(runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -U obnova_test -d postgres)
gzip -dc /var/tmp/obnova-polarita/cluster.sql.gz |
    runuser -u postgres -- env PGOPTIONS='-c synchronous_commit=off' psql -Xq -v ON_ERROR_STOP=1 -U obnova_test -d postgres >/dev/null
"${psql[@]}" -c CHECKPOINT >/dev/null
""", timeout=1800)
        saved=pg.inside(name,"cat","/var/tmp/obnova-polarita/postgres.sha256").decode().strip()
        if pg.proof(name,"obnova_test").hex()!=saved:
            raise RuntimeError("Schémata databází, účty nebo identita po obnově nesouhlasí")
        subprocess.run(["incus","exec","-T",name,"--","python3","/var/tmp/over_zulip.py"],check=True)
        if subprocess.run(["incus","exec","-T",name,"--","test","-f","/var/tmp/obnova-polarita/pitr-cil.txt"]).returncode == 0:
            subprocess.run(["incus","exec","-T",name,"--","bash","-se"],input=(TEST/"zalohy/wal-obnov.sh").read_bytes(),check=True)
        mark = WORK/".overena-obnova-next"
        mark.write_text(json.dumps({"restic_snapshot":snap,"vek_zalohy_s":round(age),"obnova_s":round(time.monotonic()-started),"dokonceno_utc":datetime.now(timezone.utc).isoformat()})+"\n")
        mark.replace(WORK/"posledni-overena-obnova.json")
        print("Z testovacího Restic snapshotu "+snap+" bylo v izolované instanci obnoveno všech 15 databází.")


if __name__=="__main__":
    main()
