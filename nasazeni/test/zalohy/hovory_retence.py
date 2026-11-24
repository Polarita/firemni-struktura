"""Běží pouze na místním cíli. Denní repo zanikne při začátku 90. dne po dni pořízení UTC."""
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shutil
import socket
import sys

STORE = Path("/var/lib/restic-test/data/polarita-test")


def prune(today, probe=None):
    if socket.gethostname().split(".")[0] != "restic-test" or not os.path.ismount("/var/lib/restic-test"):
        raise RuntimeError("Výmaz vyžaduje datový svazek samostatného záložního cíle")
    prefix = "hovory-"
    if probe is not None:
        if not re.fullmatch("[0-9a-f]{24}",probe):
            raise ValueError("Neplatná testovací skupina")
        prefix = "zkouska-hovory-"+probe+"-"
    removed = 0
    for folder in STORE.iterdir():
        name = folder.name.removeprefix(".expirace-")
        if not re.fullmatch(re.escape(prefix)+r"\d{4}-\d{2}-\d{2}",name):
            continue
        captured_day = date.fromisoformat(name[-10:])
        if today < captured_day+timedelta(days=90):
            continue
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError("Neočekávaný typ cesty na místním záložním cíli")
        pending = STORE/(".expirace-"+name)
        if folder != pending:
            folder.rename(pending)
        shutil.rmtree(pending)
        removed += 1
    print("Počet vyřazených denních repozitářů běžných hovorů:",removed)


if __name__ == "__main__":
    if len(sys.argv)==1:
        prune(datetime.now(timezone.utc).date())
    elif len(sys.argv)==4 and sys.argv[1]=="--zkouska":
        prune(date.fromisoformat(sys.argv[3]),sys.argv[2])
    else:
        raise SystemExit("Neplatné argumenty retence")
