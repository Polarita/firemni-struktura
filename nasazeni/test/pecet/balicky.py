"""Stáhne ve VM přesně zamčené distribuce pro offline instalaci do pracovní instance."""
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

src = Path(__file__).resolve().parent
target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
files = json.loads((src / "wheels.lock.json").read_text())
files["pip-26.3-py3-none-any.whl"] = {"name": "pip", "version": "26.3",
    "sha256": "f3b60b20ffaadd4415ed7957212a38ac63fa4c5fa375bd0f4a797777940fad13"}
for name, entry in files.items():
    path = target / name
    if name != Path(name).name:
        raise ValueError("Neplatný název balíčku")
    if path.is_file():
        with path.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() == entry["sha256"]:
                continue
    with urlopen(f"https://pypi.org/pypi/{entry['name']}/{entry['version']}/json", timeout=30) as res:
        link = next(x for x in json.load(res)["urls"] if x["filename"] == name)
    url = urlsplit(link["url"])
    if url.scheme != "https" or url.hostname != "files.pythonhosted.org" or link["digests"]["sha256"] != entry["sha256"]:
        raise RuntimeError("Dodavatel vrátil jiný soubor " + name)
    temp = path.with_suffix(".novy")
    with urlopen(link["url"], timeout=60) as res, temp.open("wb") as writer:
        while chunk := res.read(1024 * 1024):
            writer.write(chunk)
    with temp.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != entry["sha256"]:
            raise RuntimeError("Nesouhlasí kontrolní součet " + name)
    os.replace(temp, path)
