"""Ověří CAD přílohy přes nainstalovaný příjem, antivir, převod a běžnou výstupní frontu."""
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

BASE = Path("/srv/polarita/workspace/karantena")
PROOF = Path("/srv/polarita/workspace/dukazy/blok-10")
ACCEPT = "/srv/polarita/infra/karantena-test/bin/prijem.py"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check(sample, job):
    receipt = BASE / "protokoly" / (job + ".json")
    # Hodinový časovač vrací přechodně nedokončenou úlohu do stejné fronty.
    deadline = time.monotonic() + 720 + 3 * 1620
    retry = False
    while time.monotonic() < deadline:
        if receipt.exists():
            report = json.loads(receipt.read_text())
            if report["stav"] == "ceka":
                if not retry:
                    deadline += 2 * 3600 + 1620
                    retry = True
                    print(f"Karanténa zopakuje příjem {job}, důvod {report['duvod']}.", flush=True)
            elif report["stav"] != "ocisteno":
                raise RuntimeError(f"Karanténa ukončila {job} ve stavu {report['stav']}, důvod {report['duvod']}.")
            elif (BASE / "prijate" / job).is_file():
                break
        time.sleep(3)
    else:
        raise TimeoutError("Karanténa nedokončila zkoušku CAD.")
    pdf = BASE / "vysledky" / (Path(job).stem + ".pdf")
    with pdf.open("rb") as stream:
        is_pdf = stream.read(5) == b"%PDF-"
    digest = sha(sample)
    if (not is_pdf or report["typ"] != "pdf" or report["duvod"] != "dokonceno"
            or report["otisk_vstupu"] != digest or sha(BASE / "prijate" / job) != digest
            or report["otisk_vystupu"] != sha(pdf) or not 0 <= report["signatury_hodin"] <= 168):
        raise ValueError("Vstupní výkres, výstupní PDF a doklad pracovníka se neshodují.")
    print(f"{sample.suffix[1:].upper()} prošel frontou, antivirem a rastrovou rekonstrukcí. "
          f"Příjem {job}, SHA-256 výsledku {report['otisk_vystupu']}.", flush=True)


def main(revision):
    if socket.gethostname().split(".")[0] != "polarita-hq" or not re.fullmatch(r"[0-9a-f]{64}", revision):
        sys.exit("Ověření vyžaduje připravené CAD vzory ve firemní VM.")
    directory = PROOF / ("cad-" + revision)
    subprocess.run(["sha256sum", "--strict", "--status", "-c", "SHA256SUMS"], cwd=directory, check=True)
    jobs = []
    for kind in ("dxf", "ifc", "dwg"):
        sample = directory / ("vzor." + kind)
        with sample.open("rb") as stream:
            job = subprocess.check_output([sys.executable, ACCEPT, kind], stdin=stream, text=True).strip()
        if not re.fullmatch(r"[0-9a-f]{32}\." + kind, job):
            raise ValueError("Fronta nevydala potvrzení příjmu CAD.")
        jobs.append((sample, job))
        print("Zařazen výkres", job, flush=True)
    for sample, job in jobs:
        check(sample, job)


if __name__ == "__main__":
    main(sys.argv[1])
