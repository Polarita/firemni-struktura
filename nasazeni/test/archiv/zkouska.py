"""Praktická zkouška ochrany již autorizovaného vzorového listu deníku."""
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import uloz


def main():
    uloz.check_host()
    source = Path("/srv/polarita/workspace/dukazy/blok-04/pecet/archivni-kopie-deniku.pdf")
    content = source.read_bytes()
    worker = ["incus", "exec", "-T", "pecet-test"]
    app = ["--", "/opt/polarita-pecet/bin/python", "/opt/polarita-pecet/dokument.py"]
    root = subprocess.check_output(worker + ["--user", "65534", "--group", "65534"] + app + ["--verejny-koren"]).decode().strip()
    subprocess.run(worker + ["--user", "65533", "--group", "65533"] + app + ["--overit"],
                   input=json.dumps({"pdf": base64.b64encode(content).decode(), "ca": root}).encode(),
                   stdout=subprocess.DEVNULL, check=True)
    digest = hashlib.sha256(content).hexdigest()
    for area in uloz.AREAS:
        uloz.archive_dir(uloz.DATA / area)
    year = datetime.now(timezone.utc).year
    args = (source, "stavebni-deniky-10let", "pdf", digest, year)
    final, snapshot = uloz.store(*args)
    if uloz.store(*args) != (final, snapshot):
        raise RuntimeError("Opakování vytvořilo nový objekt")
    historical = uloz.DATA / ".zfs/snapshot" / snapshot.split("@")[1] / final.relative_to(uloz.DATA)
    with historical.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != digest:
            raise RuntimeError("Uložený snímek se liší od dokumentu")
    subprocess.run(["runuser", "-u", uloz.READER, "--", "python3", "-c", """
import hashlib, os, sys
from pathlib import Path
p = Path(sys.argv[1])
assert hashlib.sha256(p.read_bytes()).hexdigest() == sys.argv[2]
for action in (lambda: os.close(os.open(p, os.O_WRONLY)), p.unlink):
    try: action()
    except PermissionError: continue
    raise RuntimeError("Účet mohl změnit vzorový archiv")
""", str(final), digest], check=True)
    print("Ověřená archivní kopie deníku je čitelná. Přepsání a smazání pod archivním účtem bylo zamítnuto.")
    print("Stejný požadavek vrátil stejný objekt. Kontrolní součet souhlasí i ze snímku chráněného zfs hold.")


if __name__ == "__main__":
    main()
