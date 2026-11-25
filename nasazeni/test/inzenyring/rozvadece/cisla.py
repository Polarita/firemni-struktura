"""Prověří souběžné přidělení výrobních čísel ve dvou skutečných testovacích spisech."""
from concurrent.futures import ThreadPoolExecutor
import re
import socket
import subprocess
from uuid import UUID, NAMESPACE_URL, uuid5


def sql(command, **fields):
    args = ["runuser","-u","postgres","--","psql","-XAtqw","-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik"]
    for key, value in fields.items():
        args.extend(["-v", f"{key}={value}"])
    return subprocess.run(args,input=command,text=True,capture_output=True,check=True,timeout=90).stdout.strip()


def pridel(inputs):
    key, case, name = inputs
    return sql("SET ROLE pol_metadata_ddl; SELECT polarita_registr_test.pridel_rozvadec(:'key',:'case',:'name');",
               key=key,case=case,name=name)


def main(cases):
    if socket.gethostname().split(".")[0]!="postgres-test" or len(cases)!=2 or cases[0]==cases[1]:
        raise ValueError("Zkouška vyžaduje dva samostatné spisy v testovací databázi.")
    items=[(uuid5(NAMESPACE_URL, f"polarita.test/rozvadece/{case}/RP1"),case,"RP1") for case in cases]
    with ThreadPoolExecutor(max_workers=4) as pool:
        a,b,c,d = pool.map(pridel,[items[0],items[1],items[0],items[1]])
    if a!=c or b!=d or a==b or not all(re.fullmatch(r"RZ-[0-9]{4}-[0-9]{5}",n) for n in (a,b)):
        raise RuntimeError("Při souběhu nevznikla dvě stabilní různá výrobní čísla.")
    base=items[0]
    for conflict in ((base[0],items[1][1],base[2]),(uuid5(base[0],"kolize"),base[1],base[2])):
        try:
            pridel(conflict)
        except subprocess.CalledProcessError as err:
            if "23505" not in err.stderr and "duplicate key" not in err.stderr and "Stejný požadavek" not in err.stderr:
                raise
        else:
            raise RuntimeError("Přidělení přijalo kolidující údaje.")
    if pridel(items[0])!=a or pridel(items[1])!=b:
        raise RuntimeError("Po kolizi se změnila výrobní čísla.")
    for inputs,serial in zip(items,(a,b)):
        case=sql("SET ROLE pol_metadata_read; SELECT case_id FROM polarita_test_spisy.vyrobni_cisla WHERE pozadavek=:'id' AND vyrobni_cislo=:'serial';", id=inputs[0],serial=serial)
        if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}",case):
            raise ValueError("Čtená vazba výrobního čísla na spis neodpovídá.")
        print(case,inputs[2],serial,flush=True)


if __name__ == "__main__":
    import sys
    main([UUID(raw) for raw in sys.argv[1:]])
