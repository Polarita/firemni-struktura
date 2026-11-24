"""Předá pouze očištěnou kopii známého testovacího protokolu ke skutečnému OCR."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import uuid

if socket.gethostname().split(".")[0] != "polarita-hq":
    raise RuntimeError("Zkouška patří do polarita-hq")

proof = Path("/srv/polarita/workspace/dukazy/blok-04/pecet/predavaci-protokol.pdf")
queue = Path("/srv/polarita/workspace/karantena")
work = Path("/srv/polarita/infra/paperless-test")
with (work / ".vzor").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    fixture = proof.read_bytes()
    for source in sorted((queue / "prijate").glob("*.pdf"), key=lambda path: path.stat().st_mtime_ns):
        if not re.fullmatch(r"[0-9a-f]{32}\.pdf", source.name) or source.stat().st_size != len(fixture):
            continue
        if source.read_bytes() != fixture:
            continue
        report = json.loads((queue / "protokoly" / (source.name + ".json")).read_bytes())
        if report.get("stav") == "ocisteno" and report.get("typ") == "pdf":
            cleaned = queue / "vysledky" / source.name
            break
    else:
        raise RuntimeError("Chybí ověřená rekonstrukce testovacího protokolu")
    with cleaned.open("rb") as output:
        checksum = hashlib.file_digest(output, "sha256").hexdigest()
    if checksum == hashlib.sha256(fixture).hexdigest():
        raise RuntimeError("Karanténa vrátila původní PDF")
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
    with cleaned.open("rb") as pdf:
        subprocess.run(["incus", "exec", "-T", "paperless-test", "--", "/command/with-contenv",
            "/command/s6-setuidgid", "paperless", "python3", inside, case, checksum],
            stdin=pdf, check=True, timeout=1800)
