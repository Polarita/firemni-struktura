"""Porovná denní počty převzetí s Umami. Přílohy ani údaje o klientech neopouštějí spis."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    if os.geteuid() or os.uname().nodename.split(".")[0] != "polarita-hq":
        raise SystemExit("Sběr patří do virtuálního ředitelství.")
    output = Path("/var/lib/polarita-umami-test")
    output.mkdir(mode=0o755, exist_ok=True)
    with Path("/run/polarita-umami-overeni.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        query = """SELECT (prijato AT TIME ZONE 'UTC')::date, count(*)
                   FROM polarita_test_spisy.potvrzeni_sanonu GROUP BY 1 ORDER BY 1"""
        lines = subprocess.check_output(["incus","exec","-T","postgres-test","--","runuser","-u",
                        "pol_metadata_read","--","psql","-XqAtw","-d","db_erp_lhutnik","-c",query], text=True)
        rows = []
        for line in lines.splitlines():
            day, count = line.split("|")
            rows.append({"day": day, "received": int(count)})
        data = {"password": Path("/srv/polarita/data/bootstrap-test/test-login/heslo").read_text().strip(),
                "rows": rows}
        result = subprocess.run(["incus","exec","-T","umami-test","--user","1001","--group","1001",
                                 "--","node","/etc/polarita-umami/over.mjs","--import"],
                                input=json.dumps(data), text=True, stdout=subprocess.PIPE, check=True)
        report = json.loads(result.stdout)
        if report["days"] != rows or report["available"] is not True or report["event"] != "prevzeti-sanonu":
            raise RuntimeError("Analytika nepotvrdila výsledky registru.")
        with tempfile.NamedTemporaryFile("w", dir=output, delete=False) as tmp:
            json.dump(report, tmp, ensure_ascii=False)
            os.fchmod(tmp.fileno(), 0o644)
        os.replace(tmp.name, output/"konverze.json")
        print(f"Převzetí potvrzená zdrojovým registrem a Umami: {sum(r['received'] for r in rows)}. Počet dnů: {len(rows)}.")


if __name__ == "__main__":
    main()
