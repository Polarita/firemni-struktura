"""Trvalé syntetické doklady a transakční zkoušky společných číselných řad."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from uuid import uuid5

from spisy_rz import id_spisu
from vzorove_doklady import doklady


def sql(dotaz, *, chyba=None, **parametry):
    args = ["runuser","-u","postgres","--","psql","-XqAtw","-d","db_erp_lhutnik",
            "-v","ON_ERROR_STOP=1","-v","VERBOSITY=sqlstate"]
    for k,v in parametry.items():
        args.extend(["-v", k+"="+str(v)])
    r = subprocess.run(args,input=dotaz,text=True,capture_output=True,timeout=60)
    if chyba:
        if r.returncode == 0 or not re.search(r"\b"+chyba+r"\b",r.stderr):
            raise RuntimeError(f"Databáze měla odmítnout operaci se stavem {chyba}: {r.stderr[:300]}")
    elif r.returncode:
        raise RuntimeError("Registr odmítl operaci: "+r.stderr[:300])
    return r.stdout.strip()


PRIDEL = """SET LOCAL ROLE pol_registr_doklady;
SELECT polarita_registr_test.pridel_doklad(:'klic',:'spis',:'druh',:'otisk');"""


def pridel(row):
    return sql("BEGIN;"+PRIDEL+"COMMIT;",**row)


def over():
    if socket.gethostname().split(".")[0] != "postgres-test":
        raise RuntimeError("Zkouška patří do postgres-test.")
    rows = doklady(json.loads(Path(__file__).with_name("vzory.json").read_bytes()))
    with ThreadPoolExecutor(max_workers=6) as pool:
        vysledky = list(pool.map(pridel, rows + rows[::-1]))
    cisla = vysledky[:len(rows)]
    if len(set(cisla)) != len(rows) or cisla != vysledky[len(rows):][::-1]:
        raise RuntimeError("Souběh přidělil jiná nebo duplicitní čísla.")
    for row,cislo in zip(rows,cisla):
        if not re.fullmatch(row["druh"]+r"-[0-9]{4}-[0-9]{5}",cislo):
            raise ValueError("Chybný formát čísla.")
        stav = sql("""SET ROLE pol_metadata_read; SELECT case_id FROM polarita_registr_test.prehled_dokladu
                    WHERE case_id=(SELECT case_id FROM polarita_test_spisy.karty WHERE pozadavek=:'uid') AND cislo=:'cislo' AND podklad_sha256=:'otisk';""",cislo=cislo,otisk=row["otisk"],uid=row["spis"])
        if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}",stav):
            raise ValueError("Chybí čtená vazba na spis.")
        print(stav,cislo,row["otisk"])
    a = rows[0]
    for delta in ({"otisk":"0"*64}, {"druh":"VYD"}, {"spis":rows[-1]["spis"]}):
        sql("BEGIN;"+PRIDEL+"ROLLBACK;",chyba="23505",**{**a,**delta})
    sql("BEGIN;"+PRIDEL+"ROLLBACK;",chyba="23503",**{**a,"klic":str(uuid5(id_spisu("kladny"),"neplatny")),
        "spis":"00000000-0000-0000-0000-000000000000"})
    sql("BEGIN; SET LOCAL ROLE pol_metadata_api; SELECT polarita_registr_test.pridel_doklad(:'klic',:'spis',:'druh',:'otisk'); ROLLBACK;",
        chyba="42501",**a)
    sql("BEGIN; SET LOCAL ROLE pol_registr_doklady; UPDATE polarita_registr_test.rada SET posledni=0 WHERE false; ROLLBACK;",
        chyba="42501")
    prehled = sql("""
WITH rady AS (
  SELECT druh, rok, posledni FROM polarita_registr_test.rada
  UNION ALL SELECT 'POL',rok,posledni FROM polarita_test_spisy.rada
  UNION ALL SELECT 'RZ',rok,posledni FROM polarita_test_spisy.vyrobni_rada
), vydane AS (
  SELECT druh,rok,poradi FROM polarita_registr_test.doklad
  UNION ALL SELECT 'POL',rok,cislo FROM polarita_test_spisy.spis
  UNION ALL SELECT 'RZ',rok,poradi FROM polarita_test_spisy.rozvadec
)
SELECT r.druh,r.rok,r.posledni,count(v.poradi),count(DISTINCT v.poradi),
       coalesce(min(v.poradi),0),coalesce(max(v.poradi),0)
FROM rady r LEFT JOIN vydane v USING(druh,rok) GROUP BY r.druh,r.rok,r.posledni ORDER BY r.druh,r.rok;
""")
    druhy = set()
    for line in prehled.splitlines():
        druh,rok,konec,pocet,unikat,minimum,maximum = line.split("|")
        if not (konec == pocet == unikat == maximum and int(minimum) == int(int(konec)>0)):
            raise ValueError("Nespojitá nebo duplicitní řada "+druh+" "+rok)
        druhy.add(druh)
        print(druh,rok,"· čísel bez mezer nebo duplicit:",pocet)
    if druhy != {"FAK","ORG-UOL","VYD","POL","RZ"}:
        raise ValueError("Zkouška nezahrnula všech pět řad.")


if __name__ == "__main__":
    over()
