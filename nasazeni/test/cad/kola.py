"""Připrav ověřené binární balíčky pro offline Python 3.14 na amd64."""
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(cache):
    if sys.version_info[:2] != (3, 14) or platform.machine() != "x86_64":
        raise RuntimeError("Balíčky CAD vyžadují CPython 3.14 pro amd64.")
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    for line in Path(__file__).with_name("kola.lock").read_text().splitlines():
        url, digest = line.split("#sha256=")
        parts = urlsplit(url)
        name = Path(parts.path).name
        if (parts.scheme != "https" or parts.netloc != "files.pythonhosted.org"
                or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", name) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("Neplatný záznam v seznamu balíčků CAD.")
        target = cache / name
        if target.is_file() and checksum(target) == digest:
            continue
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
            tmp = Path(stream.name)
            try:
                with urlopen(url, timeout=90) as source:
                    shutil.copyfileobj(source, stream)
                stream.flush()
                if checksum(tmp) != digest:
                    raise ValueError(f"Nesouhlasí SHA-256 balíčku {name}.")
                os.replace(tmp, target)
            finally:
                tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
