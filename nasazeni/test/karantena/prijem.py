"""Přijme obsah na stdin a zařadí atomicky dokončený soubor do karantény firemní VM."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile

BASE = Path("/srv/polarita/workspace/karantena")
LIMIT = 64 * 1024 * 1024


def enqueue(source, kind):
    if socket.gethostname().split(".")[0] != "polarita-hq" or kind not in {"pdf", "txt", "wav", "dxf", "ifc", "dwg"}:
        raise ValueError("Neplatný vstup karantény")
    incoming = BASE / "vstup"
    incoming.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = secrets.token_hex(16) + "." + kind
    size = 0
    with tempfile.NamedTemporaryFile(dir=incoming, prefix=".prijem-", delete=False) as f:
        tmp = Path(f.name)
        try:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > LIMIT:
                    raise ValueError("Příloha přesahuje 64 MiB")
                f.write(chunk)
            if not size:
                raise ValueError("Prázdná příloha")
            f.flush()
            os.fsync(f.fileno())
            tmp.replace(incoming / token)
        finally:
            tmp.unlink(missing_ok=True)
    return token


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("typ", choices=("pdf", "txt", "wav", "dxf", "ifc", "dwg"))
    args = parser.parse_args()
    print(enqueue(sys.stdin.buffer, args.typ))
