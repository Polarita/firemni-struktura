"""Restic otevře přes ověřené TLS vlastní snapshot a obnoví obsah přímo do instance bez síťové karty."""
from contextlib import ExitStack
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

from sber import CA,WORK,TEST,pg,provoz,rest_env


def main():
    if os.geteuid() or socket.gethostname().split(".")[0]!="polarita-hq":
        raise RuntimeError("Obnova patří do firemní VM")
    os.umask(0o077)
    snap=(WORK/"posledni-otisk").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{64}",snap):
        raise RuntimeError("Chybí dokončená testovací záloha")
    image=pg.run("incus","config","get",pg.DB,"volatile.base_image").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}",image):
        raise RuntimeError("Chybí lokální obraz cílové databáze")
    name="restic-obnova-"+secrets.token_hex(6)
    with ExitStack() as stack:
        lock=stack.enter_context((WORK/".obnova").open("a"))
        fcntl.flock(lock,fcntl.LOCK_EX)
        pg.run("incus","init",image,name,"-p","default","-p","sandbox_airgap","-c","limits.memory=384MiB")
        stack.callback(pg.run,"incus","delete","--force",name)
        pg.run("incus","start",name)
        pg.start_restore_cluster(name)
        subprocess.run(["bash",str(TEST/"incus/balicky.sh"),name,"git=1:2.53.0-1ubuntu1.1"],check=True,stdout=subprocess.DEVNULL)
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
        subprocess.run(["incus","exec","-T",name,"--","python3","/var/tmp/over_soubory.py"],check=True)
        subprocess.run(["incus","file","push","--mode=0400",str(TEST/"zalohy/obnov_raft.py"),name+"/run/obnov_raft.py"],check=True)
        seal = pg.run("systemd-creds","decrypt","--name=bao-pecet",str(provoz.p.VAULT/"pecet.cred"),"-")
        payload = {"seal":base64.b64encode(seal).decode(),"manager":provoz.p.recover("bao-sprava")}
        subprocess.run(["incus","exec","-T",name,"--","python3","/run/obnov_raft.py"],
                       input=json.dumps(payload).encode(), check=True, timeout=180)
        pg.inside(name,"bash","-ec","set -o pipefail; gzip -dc /var/tmp/obnova-polarita/cluster.sql.gz | runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -U obnova_test -d postgres >/dev/null")
        saved=pg.inside(name,"cat","/var/tmp/obnova-polarita/postgres.sha256").decode().strip()
        if pg.proof(name,"obnova_test").hex()!=saved:
            raise RuntimeError("Schémata databází, účty nebo identita po obnově nesouhlasí")
        if subprocess.run(["incus","exec","-T",name,"--","test","-f","/var/tmp/obnova-polarita/pitr-cil.txt"]).returncode == 0:
            subprocess.run(["bash",str(TEST/"incus/balicky.sh"),name,"pgbackrest=2.58.0-1"],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(["incus","exec","-T",name,"--","bash","-se"],input=(TEST/"zalohy/wal-obnov.sh").read_bytes(),check=True)
        mark = WORK/".overena-obnova-next"
        mark.write_text(json.dumps({"restic_snapshot":snap})+"\n")
        mark.replace(WORK/"posledni-overena-obnova.json")
        print("Z testovacího Restic snapshotu "+snap+" bylo v izolované instanci obnoveno všech 15 databází.")


if __name__=="__main__":
    main()
