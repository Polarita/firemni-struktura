"""Přenese pouze doložený výstup karantény do archivu a zapíše skutečný výsledek OCR."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import UUID, NAMESPACE_URL, uuid5

QUEUE = Path("/srv/polarita/workspace/karantena")
WORK = Path("/srv/polarita/infra/paperless-test")

def query(sql, **fields):
    cmd = ["incus","exec","-T","postgres-test","--","runuser","-u","pol_prijem_sanonu","--",
           "psql","-XAtqw","-v","ON_ERROR_STOP=1","-d","db_erp_lhutnik"]
    for key, value in fields.items():
        cmd.extend(["-v", key + "=" + str(value)])
    result = subprocess.run(cmd, input=sql, text=True, capture_output=True, timeout=45, check=True)
    return result.stdout.strip()

def process(row):
    key = str(UUID(row["priloha"]))
    case = row["case_id"]
    sha = row["otisk"]
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case) or not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise ValueError("Neočekávaný identifikátor")
    job = uuid5(NAMESPACE_URL, "polarita.test/sanony/"+key).hex + ".pdf"
    receipt = QUEUE / "protokoly" / (job + ".json")
    if not receipt.exists():
        return
    report = json.loads(receipt.read_bytes())
    if report["stav"] == "ceka":
        return
    archive = {"ocisteno":"prijate", "odmitnuto":"odmitnute"}[report["stav"]]
    original = QUEUE / archive / job
    if not original.is_file():
        return
    with original.open("rb") as f:
        if original.stat().st_size != row["bajtu"] or hashlib.file_digest(f,"sha256").hexdigest() != sha:
            raise ValueError("Otisk přijatého šanonu nesouhlasí s registrem")
    if report.get("otisk_vstupu", sha) != sha:
        raise ValueError("Doklad karantény náleží jinému vstupu")
    fields = dict(id=key, kod=case, puvodni=sha, cisty="", doc="", stav="odmitnuto")
    if archive == "prijate":
        if report.get("typ") != "pdf":
            raise ValueError("Doklad nepatří vyčištěnému PDF")
        with (QUEUE / "vysledky" / job).open("rb") as pdf:
            digest = hashlib.file_digest(pdf,"sha256").hexdigest()
            if digest == sha or digest != report.get("otisk_vystupu", digest):
                raise ValueError("Otisk výstupu pracovníka karantény nesouhlasí")
            pdf.seek(0)
            command = ["incus","exec","-T","paperless-test","--","/command/with-contenv","/command/s6-setuidgid",
                       "paperless","python3","/etc/polarita-paperless/prijmi_dokument.py",case,digest,"--sanon"]
            res = subprocess.run(command, stdin=pdf, capture_output=True, timeout=1800, check=True)
        data = json.loads(res.stdout.strip().splitlines()[-1])
        if type(data["dokument"]) is not int or data["dokument"] < 1 or type(data["ocr"]) is not bool:
            raise ValueError("Archiv nepotvrdil dokument")
        fields.update(doc=data["dokument"], cisty=digest, stav="ocr-hotovo" if data["ocr"] else "ke-kontrole")
    if query("""SELECT polarita_test_spisy.uzavri_ocr(:'id'::uuid,:'kod',:'puvodni',nullif(:'cisty',''),
              nullif(:'doc','')::bigint,:'stav');""", **fields) != "t":
        raise RuntimeError("Změnil se registr přijímaného šanonu")
    print(f"{key} {case} {fields['stav']}", flush=True)

if __name__ == "__main__":
    failed = False
    with (WORK / ".vzor").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for raw in query("SELECT to_jsonb(r) FROM polarita_test_spisy.fronta_archivu r ORDER BY prijato,priloha;").splitlines():
            row = json.loads(raw)
            try:
                process(row)
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as err:
                failed = True
                print(f"{row['priloha']} {type(err).__name__}", file=sys.stderr)
    sys.exit(1 if failed else 0)
