"""Uloží vydaný vzor Akademie do šifrovaného archivu TEST a přečte uložený snímek."""
import hashlib
from pathlib import Path
import re
import sys

import uloz


def archivuj(source, year):
    if (source.parent != Path("/srv/polarita/workspace/dukazy/blok-09")
            or not re.fullmatch(r"akademie-osvedceni-[0-9a-f]{64}\.pdf", source.name)
            or source.is_symlink() or not 2000 <= year <= 2099):
        raise ValueError("Neočekávaný doklad Akademie.")
    with source.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("Vydané osvědčení není PDF.")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    final, snapshot = uloz.store(source, "odborna-zpusobilost", "pdf", digest, year)
    saved = uloz.DATA / ".zfs/snapshot" / snapshot.split("@")[1] / final.relative_to(uloz.DATA)
    with saved.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise RuntimeError("Osvědčení v archivním snímku se liší od vydaného PDF.")
    print(f"Archiv TEST uchoval vydané PDF v agendě odborné způsobilosti pod SHA-256 {digest}. "
          "Obsah souhlasí při čtení ze snímku chráněného zfs hold.")


if __name__ == "__main__":
    archivuj(Path(sys.argv[1]), int(sys.argv[2]))
