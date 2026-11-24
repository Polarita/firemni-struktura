"""Izolovaná zkouška nad kopiemi dvaceti skutečných kvót. Bez přenosu klíčů či osobních údajů."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
from contextlib import contextmanager
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
PG = ["incus","exec","-T","postgres-test","--","runuser","-u","postgres","--"]
BIN = "/usr/lib/postgresql/18/bin/"

def sql(db, stmt, *variables, folder=None):
    endpoint = ["-h",folder] if folder else []
    result = subprocess.run([*PG,"psql","-XqAtw","-v","ON_ERROR_STOP=1",*endpoint,"-d",db,*variables],
                            input=stmt,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1200])
    return result.stdout.strip()

@contextmanager
def isolated():
    folder=subprocess.check_output([*PG,"mktemp","-d","/var/tmp/finops-pg-XXXXXXXX"],text=True).strip()
    if not re.fullmatch(r"/var/tmp/finops-pg-[A-Za-z0-9]{8}",folder):
        raise RuntimeError("Neplatná cesta izolované zkoušky")
    data=folder+"/data"
    started=False
    try:
        subprocess.run([*PG,BIN+"initdb","--no-sync","--auth-local=peer","--auth-host=reject",
                        "--encoding=UTF8","--locale=C.UTF-8","-D",data],stdout=subprocess.DEVNULL,check=True)
        options = f"-c listen_addresses='' -c unix_socket_directories={folder} -c unix_socket_permissions=0700 -c shared_buffers=8MB -c max_connections=10"
        subprocess.run([*PG,BIN+"pg_ctl","start","-w","-D",data,"-l",folder+"/postgres.log","-o",options],
                       check=True,stdout=subprocess.DEVNULL)
        started=True
        sql("postgres","CREATE DATABASE db_paperclip TEMPLATE template0",folder=folder)
        yield folder
    finally:
        if started:
            subprocess.run([*PG,BIN+"pg_ctl","stop","-m","fast","-w","-D",data],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([*PG,"rm","-r","--",folder],check=True)

def main():
    quotas = sql("db_paperclip","SELECT jsonb_agg(jsonb_build_object('pozice',pozice,'kvota',kvota) ORDER BY pozice) FROM polarita_finops.kvoty")
    if len(json.loads(quotas))!=20:
        raise RuntimeError("Chybí pozice Paperclipu")
    with isolated() as folder:
        def check(stmt, *args):
            return sql("db_paperclip",stmt,*args,folder=folder)
        check((ROOT/"vzor.sql").read_text(), "-v", "kvoty="+quotas)
        check((ROOT/"rozpocet.sql").read_text())
        check((ROOT/"zkouska.sql").read_text())
        check((ROOT/"zkouska_p1.sql").read_text())
        task = uuid4()
        def reserve():
            return check(f"SET ROLE pol_finops_call; SELECT polarita_finops.rezervuj('{uuid4()}','11001','{task}','provoz',2975)")
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(reserve) for _ in range(2)]
            if sorted(job.result() for job in jobs)!=["AGENT_QUOTA_EXHAUSTED","BUDGET_OK"]:
                raise RuntimeError("Dvě souběžná volání nezastavil jediný limit")
    print("Izolovaná databáze TEST ověřila kvóty všech 20 pozic, souběh dvou čerpání, vyúčtování, rezervu P1, varování 80 % a společnou stopku 470 USD.")


if __name__ == "__main__":
    main()
