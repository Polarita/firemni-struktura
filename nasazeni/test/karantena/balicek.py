"""Ověří podepsaný index výrobce a SHA-256 offline balíčku Dangerzone pro Ubuntu 26.04."""
import gzip
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

BASE = "https://packages.freedom.press/apt-tools-prod/"
SIGNER = "DE28AB241FA48260FAC9B8BAA7C9B38522604281"
DOC = "dists/resolute/"
DEB = "dangerzone-full_0.11.1_amd64.deb"
PIN = "0ae0a0db9befc71afcff1af0c65400d61af8f923c6100c4c77d5866b11da80da"


def fetch(url, target):
    subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
                    "--proto-redir", "=https", "--retry", "2", "--max-time", "480", "-o", target, url], check=True)


def main():
    directory = Path(sys.argv[1])
    directory.mkdir(exist_ok=True, parents=True)
    final = directory / DEB
    if final.exists():
        with final.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() == PIN:
                return
    with TemporaryDirectory(dir=directory) as d:
        tmp = Path(d)
        fetch("https://keys.openpgp.org/vks/v1/by-fingerprint/" + SIGNER, tmp / "fpf.asc")
        keys = subprocess.check_output(["gpg", "--homedir", d, "--batch", "--show-keys", "--with-colons", tmp / "fpf.asc"], text=True)
        fingerprints = [row.split(":")[9] for row in keys.splitlines() if row.startswith("fpr:")]
        if not fingerprints or fingerprints[0] != SIGNER or keys.count("pub:") != 1:
            raise RuntimeError("Chybný podpisový klíč")
        subprocess.run(["gpg", "--homedir", d, "--batch", "--dearmor", "-o", tmp / "fpf.gpg", tmp / "fpf.asc"], check=True)
        for part in ("Release", "Release.gpg"):
            fetch(BASE + DOC + part, tmp / part)
        subprocess.run(["gpgv", "--keyring", str(tmp / "fpf.gpg"), tmp / "Release.gpg", tmp / "Release"], check=True)
        release = (tmp / "Release").read_text()
        expiry = next(line.partition(": ")[2] for line in release.splitlines() if line.startswith("Valid-Until:"))
        if parsedate_to_datetime(expiry) <= datetime.now(timezone.utc):
            raise RuntimeError("Podepsaný index je prošlý")
        index = "main/binary-amd64/Packages.gz"
        expected = next(line.split()[0] for line in release.split("\nSHA256:\n", 1)[1].splitlines()
                        if line.strip().endswith(" " + index))
        fetch(BASE + DOC + index, tmp / "index")
        compressed = (tmp / "index").read_bytes()
        if hashlib.sha256(compressed).hexdigest() != expected:
            raise RuntimeError("Index nesouhlasí s podpisem")
        records = gzip.decompress(compressed).decode().split("\n\n")
        rec = next(entry for entry in records if entry.startswith("Package: dangerzone-full\n") and "\nVersion: 0.11.1\n" in entry)
        meta = dict(line.split(": ", 1) for line in rec.splitlines() if ": " in line and not line.startswith(" "))
        if meta["SHA256"] != PIN or meta["Filename"] != "pool/main/d/dangerzone/" + DEB:
            raise RuntimeError("Balíček nesouhlasí se zámkem")
        download = tmp / DEB
        fetch(BASE + meta["Filename"], download)
        with download.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != PIN:
                raise RuntimeError("Vadná kopie instalačního balíčku")
        download.replace(final)


if __name__ == "__main__":
    main()
