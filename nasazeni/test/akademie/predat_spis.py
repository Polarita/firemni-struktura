"""Předá doklady z firemní VM do spisu v Paperclipu a uloží potvrzené rozhodnutí."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile

SRC = Path(__file__).resolve().parent
PROOF = Path("/srv/polarita/workspace/dukazy/blok-09")
VM = "paperclip-test"


def give(host):
    record = json.loads((PROOF / "akademie-komise.json").read_text())
    issue = record["vydani"]
    if not re.fullmatch(r"[0-9a-f]{64}", issue):
        raise ValueError("Neplatný identifikátor vydání.")
    data = {"zaznam": record}
    for kind, filename, checksum in (("osvedceni", "osvedceni", record["osvedceni_sha256"]),
                                     ("protokol", "komise", record["protokol_sha256"])):
        pdf = (PROOF / f"akademie-{filename}-{issue}.pdf").read_bytes()
        if hashlib.sha256(pdf).hexdigest() != checksum:
            raise ValueError("Obsah přílohy se změnil po archivaci.")
        data[kind] = base64.b64encode(pdf).decode()
    run = ["incus", "exec", "-T", VM, "--"]
    dest = "/etc/polarita-paperclip/komise"
    subprocess.run([*run, "install", "-dm0755", dest], check=True)
    for src in (SRC / "rozhodnuti.py", SRC.parent / "paperclip/board.py"):
        path = dest + "/" + src.name
        subprocess.run(["incus", "file", "push", "--mode=0644", str(src), VM + path + ".next"], check=True)
        subprocess.run([*run, "mv", "-T", path + ".next", path], check=True)
    data["heslo"] = Path("/srv/polarita/data/bootstrap-test/test-login/heslo").read_text().rstrip("\r\n")
    content = subprocess.check_output(["incus", "exec", "-T", VM, "--user", "65534", "--group", "65534", "--",
        "python3", dest + "/rozhodnuti.py", host], input=json.dumps(data).encode(), timeout=300)
    receipt = json.loads(content)
    if receipt["vydani"] != issue or receipt["stav"] != "approved":
        raise ValueError("Potvrzení Decisions neodpovídá protokolu.")
    with tempfile.NamedTemporaryFile(dir=PROOF, delete=False) as writer:
        temp = Path(writer.name)
        try:
            writer.write(content)
            writer.flush()
            os.replace(temp, PROOF / "akademie-rozhodnuti.json")
        finally:
            temp.unlink(missing_ok=True)
    print(f"Spis {receipt['identifier']} obsahuje dvě z archivu ověřené PDF přílohy. "
          f"Testovací správce potvrdil rozhodnutí {receipt['approval']} a Decisions uložil jeho vazbu na spis.")


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Předání patří do TEST ředitelství.")
    with open("/run/polarita-akademie-vydani.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        give(sys.argv[1])
