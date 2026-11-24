"""Bez síťového rozhraní připraví výsledek a atomicky vystaví doklad ve výstupním svazku."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

INPUT = Path("/mnt/karantena-in")
OUTPUT = Path("/mnt/karantena-out")
JOB = re.compile(r"[0-9a-f]{32}\.(pdf|txt|wav)")

def publish(name, data):
    with tempfile.NamedTemporaryFile("w",dir=OUTPUT,delete=False) as f:
        json.dump(data,f,ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name,OUTPUT/name)

def main():
    if socket.gethostname().split(".")[0]!="karantena-test" or os.geteuid()!=17304 or os.listdir("/sys/class/net")!=["lo"]:
        raise SystemExit("Obsluha vyžaduje pracovní účet v offline VM")
    previous=None
    while True:
        if all(path.is_mount() for path in (INPUT,OUTPUT,Path("/mnt/clamav-db"))) and (INPUT/".start").is_file():
            token=(INPUT/".start").read_text().strip()
            if re.fullmatch(r"[a-f0-9]{32}",token):
                if previous!=token:
                    publish(".pripraveno",{"start":token})
                    previous=token
                for command in sorted(INPUT.glob("*.povel")):
                    src = command.with_suffix("")
                    if not JOB.fullmatch(src.name) or (OUTPUT/(src.name+".json")).exists():
                        continue
                    try:
                        if command.read_text() != token:
                            continue
                        with src.open("rb") as f:
                            digest=hashlib.file_digest(f,"sha256").hexdigest()
                    except FileNotFoundError:
                        continue
                    try:
                        run=subprocess.run(["/usr/bin/python3","/opt/polarita/karantena.py",src.name],
                                           stdin=subprocess.DEVNULL,capture_output=True,check=True,timeout=1320)
                        report=json.loads(run.stdout)
                        if isinstance(report,dict) and report.get("stav") == "ocisteno":
                            with (OUTPUT/src.name).open("rb") as f:
                                report["otisk_vystupu"] = hashlib.file_digest(f,"sha256").hexdigest()
                        if not isinstance(report,dict):
                            raise ValueError("Neplatný typ protokolu")
                    except subprocess.TimeoutExpired:
                        report={"stav":"ceka","duvod":"casovy-limit-cele-ulohy"}
                    except subprocess.CalledProcessError as exc:
                        report={"stav":"ceka","duvod":"chyba-offline-pracovnika","navrat":exc.returncode}
                    except (ValueError,OSError):
                        report={"stav":"ceka","duvod":"chyba-offline-pracovnika"}
                    publish(src.name+".json",{"start":token,"soubor":src.name,"sha256":digest,"vysledek":report})
        time.sleep(2)

if __name__=="__main__":
    main()
