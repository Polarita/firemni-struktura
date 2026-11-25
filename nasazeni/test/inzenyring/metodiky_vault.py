"""Publikace a export konkrétních Git objektů modelových metodik TEST."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

from registr_metodik import ULOZISTE, json_text, over, vydani


def sestav():
    sys.path.insert(0, "/opt/polarita-agent-vault/current")
    from pamet import ROOT, git, read, save, snapshot

    verze, vzory = vydani()
    head = save({p:v for p, (_, v) in vzory.items()}, "Založení vydání projektových metodik TEST")
    _, entries = snapshot(head=head)
    stranky = {}
    for path in sorted(vzory):
        # Poslední změna stránky zůstává stejná i po přidání jiné stránky do znalostní báze.
        rev = git(ROOT, "log", "-1", "--format=%H", head, "--", path).decode().strip()
        oid = git(ROOT, "rev-parse", "--verify", rev + ":" + path).decode().strip()
        if entries[path] != oid:
            raise ValueError("Objekt uvedený ve vydání neodpovídá revizi stránky.")
        stranky[path] = {"revize":rev, "objekt":oid, "text":read(oid)}
    balik = {"vydani":verze, "stranky":stranky}
    over(balik)
    return balik


def prijmi(balik):
    over(balik)
    adresar = ULOZISTE / balik["vydani"]
    adresar.mkdir(parents=True, exist_ok=True, mode=0o755)
    target = adresar / "registr.json"
    digest = sha256(json_text(balik).encode()).hexdigest()
    raw = json_text({"sha256":digest,"registr":balik}).encode()
    with tempfile.NamedTemporaryFile(dir=adresar, delete=False) as f:
        path = Path(f.name)
        try:
            f.write(raw)
            f.flush()
            os.fchmod(f.fileno(), 0o644)
            os.fsync(f.fileno())
            try:
                os.link(path, target)
            except FileExistsError:
                pass
            if target.is_symlink() or target.read_bytes() != raw:
                raise ValueError("Již instalované vydání báze má jiný obsah.")
        finally:
            path.unlink()
    for jmeno, stranka in balik["stranky"].items():
        print(jmeno, stranka["revize"], stranka["objekt"])


if __name__ == "__main__":
    if sys.argv[1:] == ["--zapis"]:
        print(json_text(sestav()))
    elif sys.argv[1:] == ["--prijmi"]:
        prijmi(json.load(sys.stdin))
    else:
        raise SystemExit("Očekáván režim --zapis nebo --prijmi.")
