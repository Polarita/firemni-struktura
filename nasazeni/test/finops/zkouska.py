"""Izolovaná zkouška nad kopiemi dvaceti skutečných kvót. Bez přenosu klíčů či osobních údajů."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
BASE = ["incus","exec","-T","postgres-test","--","runuser","-u","postgres","--","psql",
        "-XqAt","-v","ON_ERROR_STOP=1","-d"]


def sql(db, stmt, *variables):
    result = subprocess.run([*BASE, db, *variables], input=stmt, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1200])
    return result.stdout.strip()


def main():
    db = "pol_finops_zk_"+uuid4().hex
    quotas = sql("db_paperclip","SELECT jsonb_agg(jsonb_build_object('pozice',pozice,'kvota',kvota) ORDER BY pozice) FROM polarita_finops.kvoty")
    if len(json.loads(quotas))!=20:
        raise RuntimeError("Chybí pozice Paperclipu")
    sql("postgres", f"CREATE DATABASE {db} TEMPLATE template0")
    try:
        sql(db, (ROOT/"vzor.sql").read_text(), "-v", "kvoty="+quotas)
        sql(db, (ROOT/"rozpocet.sql").read_text())
        sql(db, (ROOT/"zkouska.sql").read_text())
        sql(db, (ROOT/"zkouska_p1.sql").read_text())
        task = uuid4()
        def reserve():
            return sql(db,f"SET ROLE pol_finops_call; SELECT polarita_finops.rezervuj('{uuid4()}','11001','{task}','provoz',2975)")
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(reserve) for _ in range(2)]
            if sorted(job.result() for job in jobs)!=["AGENT_QUOTA_EXHAUSTED","BUDGET_OK"]:
                raise RuntimeError("Dvě souběžná volání nezastavil jediný limit")
    finally:
        sql("postgres", f"DROP DATABASE {db} WITH (FORCE)")
    print("Izolovaná databáze TEST ověřila kvóty všech 20 pozic, souběh dvou čerpání, vyúčtování, rezervu P1, varování 80 % a společnou stopku 470 USD.")


if __name__ == "__main__":
    main()
