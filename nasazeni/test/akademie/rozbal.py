"""Rozbalí ověřená rozšíření do umístění Moodle 5.3 s webovým kořenem public."""
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
from zipfile import ZipFile

from podklady import CACHE, LOCK, digest


def unpack(name, root, dest):
    package = CACHE / name
    if digest(package) != json.loads(LOCK.read_text())[name]["sha256"]:
        raise ValueError(f"Nesouhlasí SHA-256 {name}")
    dest.mkdir(parents=True)
    with ZipFile(package) as archive:
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).relative_to(root).parts
            if ".." in parts or (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Neočekávaný obsah archivu {name}")
            path = dest.joinpath(*parts)
            if member.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, path.open("xb") as out:
                shutil.copyfileobj(src, out)


if __name__ == "__main__":
    base = Path(sys.argv[1])
    unpack("mod_customcert-5.3.5.zip", "customcert", base / "public/mod/customcert")
    unpack("mod_offlinequiz-5.2.0.zip", "moodle-mod_offlinequiz-5.2.0", base / "public/mod/offlinequiz")
    unpack("cs-5.3.zip", "cs", base / "jazyk/cs")
