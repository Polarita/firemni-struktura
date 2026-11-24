"""Připraví ověřené veřejné balíky pro runner bez přístupu k internetu."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import urlopen
import zipfile

WORK = Path("/srv/polarita/infra/gitea-runner-test/podklady")
CHROME = "159.0.8154.6"
WHEELS = (
    ("Markdown", "3.11.3", "markdown-3.11.3-py3-none-any.whl", "e1a31a112232504d753e5c01bb8c2de90d3f0ba986b063e10770cf7695b09e73"),
    ("pypdf", "7.1.1", "pypdf-7.1.1-py3-none-any.whl", "04c5680d4b4cfa04ab505b09393fc949860c34a4dad6565284d11a2f5c3ce8b1"),
)
ZIP_SHA = "77a6442fd3c8acd3bef9e1067fc26f5ef464277d22f0e8cb58dc3e4077a3e458"
BINARY_SHA = "24eb0a14de64ab0c9c2e283a5512ca817db64af8fd853cdb4d818f19a8e23b9b"


def matches(path, expected):
    if not path.is_file():
        return False
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest() == expected


def fetch(url, path, digest):
    if matches(path, digest):
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as out:
        staged = Path(out.name)
        try:
            with urlopen(url, timeout=90) as res:
                shutil.copyfileobj(res, out)
            out.flush()
            if not matches(staged, digest):
                raise RuntimeError("Dodavatelský součet nesouhlasí: " + path.name)
            staged.chmod(0o644)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Příprava podkladů patří do firemní VM")
    wheels = WORK / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    for package, version, name, digest in WHEELS:
        if matches(wheels / name, digest):
            continue
        with urlopen(f"https://pypi.org/pypi/{package}/{version}/json", timeout=30) as res:
            release = json.load(res)
        file = next(f for f in release["urls"] if f["filename"] == name)
        origin = urlsplit(file["url"])
        if origin.scheme != "https" or origin.hostname != "files.pythonhosted.org" or file["digests"]["sha256"] != digest:
            raise RuntimeError("Neověřená distribuce Pythonu")
        fetch(file["url"], wheels / name, digest)
    archive = WORK / ("chromium-" + CHROME + ".zip")
    fetch(f"https://storage.googleapis.com/chrome-for-testing-public/{CHROME}/linux64/chrome-headless-shell-linux64.zip",
          archive, ZIP_SHA)
    with zipfile.ZipFile(archive) as z, z.open("chrome-headless-shell-linux64/chrome-headless-shell") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != BINARY_SHA:
            raise RuntimeError("Nesouhlasí ověřený program headless Chromium")
    browser = WORK / "prohlizec"
    binary = "chrome-headless-shell-linux64/chrome-headless-shell"
    if not matches(browser / binary, BINARY_SHA):
        with TemporaryDirectory(dir=WORK) as tmp, zipfile.ZipFile(archive) as z:
            stage = Path(tmp)
            for entry in z.infolist():
                name = Path(entry.filename)
                if name.is_absolute() or ".." in name.parts or name.parts[:1] != ("chrome-headless-shell-linux64",):
                    raise RuntimeError("Nečekaná cesta v dodavatelském archivu")
                z.extract(entry, stage)
            (stage / binary).chmod(0o755)
            browser.mkdir(exist_ok=True)
            (stage / "chrome-headless-shell-linux64").rename(browser / "chrome-headless-shell-linux64")
    print("Ověřeny dva offline balíky Pythonu a shodné sestavení prohlížeče pro tisk a test GUI.")


if __name__ == "__main__":
    main()
