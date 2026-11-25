"""Dvě databázová spojení závodí o 70 m z téhož 100m bubnu v TEST."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
from threading import Barrier
from uuid import uuid4

def sql(statement, *, owner=False, expected=None, **params):
    cmd = ["runuser", "-u", "postgres", "--", "psql", "-XqAtw", "-d", "db_eshop", "-v", "ON_ERROR_STOP=1"]
    for k,v in params.items():
        cmd.extend(["-v", f"{k}={v}"])
    result = subprocess.run(cmd, input="\\set VERBOSITY verbose\n" +
                            ("" if owner else "SET ROLE db_eshop;\n") + statement,
                            text=True, capture_output=True, timeout=90)
    if expected and result.returncode and expected + ":" in result.stderr:
        return expected
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()

def main():
    drum, first, second, issue, release = (str(uuid4()) for _ in range(5))
    tag = "TEST-BUBEN-" + drum
    projects = ("POL-2026-90001","POL-2026-90002")
    def reserve(i):
        barrier.wait(timeout=15)
        return sql("SELECT zbyva_mm FROM wms.rezervuj_kabel(:'rid',:'bid',:'spis',70000);",
                   expected="P1001", rid=(first,second)[i], bid=drum, spis=projects[i])
    def state():
        return sql("SELECT skladem_mm,rezervovano_mm,volno_mm FROM wms.bubny_prehled WHERE id=:'bid';",bid=drum)
    def move(key, project, action, length, expected=None, label=None):
        return sql("SELECT zbyva_mm FROM wms.pohyb_kabelu(:'key',:'rid',:'tag',:'spis',:'druh',:'mm');",
                   expected=expected,key=key,rid=rid,tag=tag if label is None else label,spis=project,druh=action,mm=length)
    receive = "SELECT prijato_mm FROM wms.prijmi_buben(:'bid',:'tag','varianta-kabel-test','MAIN-101',100000);"
    try:
        assert sql(receive,bid=drum,tag=tag)=="100000"
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve,range(2)))
        assert sorted(results)==["70000","P1001"], results
        winner = results.index("70000")
        rid = (first,second)[winner]
        own, other = projects[winner], projects[1-winner]
        assert state()=="100000|70000|30000"
        assert move(issue,other,"vydej",45250,"P0002")=="P0002"
        assert move(issue,own,"vydej",45250,"P0002",tag+"-jiny")=="P0002"
        assert move(issue,own,"vydej",71000,"P1001")=="P1001"
        assert move(issue,own,"vydej",45250)=="24750"
        assert move(issue,own,"vydej",45250)=="24750"
        assert move(issue,own,"vydej",45251,"23505")=="23505"
        assert state()=="54750|24750|30000"
        assert move(release,own,"uvolneni",24750)=="0"
        assert state()=="54750|0|54750"
        assert sql(receive,bid=drum,tag=tag)=="100000" and state()=="54750|0|54750"
        assert sql("UPDATE wms.bubny SET skladem_mm=99999 WHERE id=:'bid';",expected="42501",bid=drum)=="42501"
    finally:
        sql("""BEGIN;
            DELETE FROM wms.pohyby_kabelu WHERE id IN (:'issue',:'release') AND rezervace IN (:'first',:'second');
            DELETE FROM wms.rezervace_kabelu WHERE buben=:'bid' AND id IN (:'first',:'second');
            DELETE FROM wms.bubny WHERE id=:'bid' AND stitek=:'tag';
            COMMIT;""", owner=True,bid=drum,tag=tag,first=first,second=second,issue=issue,release=release)
    print("Buben 100 m · dvě stavby souběžně požadovaly po 70 m. Jedna rezervace uspěla.")
    print("Výdej 45,250 m proběhl jednou i po opakování. Cizí stavba, jiný buben a nadměrný výdej byly odmítnuty.")
    print("Po uvolnění zbývajících 24,750 m bylo fyzicky i volně 54,750 m. Účet aplikace nemohl přepsat zůstatek.")

if __name__ == "__main__":
    main()
