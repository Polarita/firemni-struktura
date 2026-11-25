"""Předá pouze očištěnou kopii známého testovacího protokolu ke skutečnému OCR."""
import fcntl
import hashlib
import io
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import uuid

if socket.gethostname().split(".")[0] != "polarita-hq":
    raise RuntimeError("Zkouška patří do polarita-hq")

proof = Path("/srv/polarita/workspace/dukazy/blok-04/pecet/predavaci-protokol.pdf")
queue = Path("/srv/polarita/workspace/karantena")
work = Path("/srv/polarita/infra/paperless-test")
with (work / ".vzor").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    # Obnova testovací pečeti vytvoří nové podepsané bajty. Rozpracovaná zkouška
    # pokračuje se stejným ověřeným vstupem i v případě změny vzoru na portálu.
    receipt = work / "vzor-prijem.json"
    if receipt.exists():
        chosen = json.loads(receipt.read_bytes())
    else:
        fixture = proof.read_bytes()
        original_hash = hashlib.sha256(fixture).hexdigest()
        job = None
        for known in sorted((queue / "prijate").glob("*.pdf"), key=lambda path: path.stat().st_mtime_ns):
            if re.fullmatch(r"[0-9a-f]{32}\.pdf", known.name) and known.stat().st_size == len(fixture) and known.read_bytes() == fixture:
                job = known.name
                break
        if job is None:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "karantena"))
            from prijem import enqueue
            job = enqueue(io.BytesIO(fixture), "pdf")
        chosen = {"job":job, "zdroj_sha256":original_hash}
        tmp = receipt.with_suffix(".next")
        tmp.write_text(json.dumps(chosen) + "\n")
        tmp.replace(receipt)
    job = chosen["job"]
    original_hash = chosen["zdroj_sha256"]
    if not re.fullmatch(r"[0-9a-f]{32}\.pdf", job) or not re.fullmatch(r"[0-9a-f]{64}", original_hash):
        raise RuntimeError("Poškozené potvrzení zkušebního vstupu")
    source = queue / "prijate" / job
    deadline = time.monotonic() + 2400
    while not source.exists():
        if (queue / "odmitnute" / job).exists() or time.monotonic() >= deadline:
            raise RuntimeError("Karanténa nevydala čistý protokol")
        time.sleep(5)
    with source.open("rb") as accepted:
        if hashlib.file_digest(accepted, "sha256").hexdigest() != original_hash:
            raise RuntimeError("Karanténa přijala jiný vstup")
    report = json.loads((queue / "protokoly" / (job + ".json")).read_bytes())
    if report.get("stav") != "ocisteno" or report.get("typ") != "pdf":
        raise RuntimeError("Chybí doklad úspěšné rekonstrukce PDF")
    cleaned = queue / "vysledky" / job
    with cleaned.open("rb") as output:
        checksum = hashlib.file_digest(output, "sha256").hexdigest()
    if checksum == original_hash or report.get("otisk_vystupu", checksum) != checksum:
        raise RuntimeError("Otisk očištěného PDF neodpovídá rekonstrukci")
    request = str(uuid.uuid5(uuid.NAMESPACE_URL, "polarita.test/web-spisy"))
    case = subprocess.check_output(["incus", "exec", "-T", "postgres-test", "--",
        "runuser", "-u", "pol_metadata_read", "--", "psql", "-XAtqw", "-v", "ON_ERROR_STOP=1",
        "-d", "db_erp_lhutnik", "-c", f"SELECT case_id FROM polarita_test_spisy.karty WHERE pozadavek='{request}'::uuid"],
        text=True, timeout=30).strip()
    if not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case):
        raise RuntimeError("Chybí zkušební spis ředitelství")
    inside = "/etc/polarita-paperless/over_dokument.py"
    script = Path(__file__).with_name("over_dokument.py")
    (work / "conf" / "over_dokument.py.next").write_bytes(script.read_bytes())
    (work / "conf" / "over_dokument.py.next").chmod(0o644)
    (work / "conf" / "over_dokument.py.next").replace(work / "conf" / "over_dokument.py")
    # Kapacitu získáme až po převzetí výsledku z offline VM.
    with cleaned.open("rb") as pdf, Path("/run/polarita-test-zatez.lock").open("a") as capacity:
        fcntl.flock(capacity, fcntl.LOCK_EX)
        subprocess.run(["incus", "exec", "-T", "paperless-test", "--", "/command/with-contenv",
            "/command/s6-setuidgid", "paperless", "python3", inside, case, checksum],
            stdin=pdf, check=True, timeout=1800)
    proof_file = work / "vzor-overen.json"
    tmp = proof_file.with_suffix(".next")
    tmp.write_text(json.dumps({"case_id": case, "sha256": checksum, "job": source.name}) + "\n")
    tmp.replace(proof_file)
