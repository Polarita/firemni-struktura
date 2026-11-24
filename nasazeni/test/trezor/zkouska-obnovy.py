"""Soukromý klíč testovací obnovy zůstává na Ejpovicích. Do izolované zkoušky jdou data přes rouru."""
from hashlib import file_digest
import base64
import json
import os
import tempfile
from pathlib import Path
import subprocess
import sys

if subprocess.check_output(["hostname", "-s"]).strip() != b"ejpovice":
    sys.exit("Zkouška potřebuje testovací identitu hypervizoru Ejpovice")
guest = ["incus", "exec", "-T", "--project", "polarita", "polarita-hq", "--"]
directory = Path("/etc/polarita-test-obnova")


def decrypt(name):
    archive = subprocess.check_output(guest + ["cat", "/srv/polarita/data/bootstrap-test/openbao-test/" + name])
    return subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
                           "-recip", str(directory / "test.crt"), "-inkey", str(directory / "test.key")],
                          input=archive, capture_output=True, check=True).stdout


payload = {"seal": base64.b64encode(decrypt("pecet.cms")).decode(),
           "shares": json.loads(decrypt("obnova-podily.cms"))["shares"]}
subprocess.run(guest + ["python3", sys.argv[1] + "/obnova.py"],
               input=json.dumps(payload).encode(), check=True)

# Jedna atomická kopie ověřeného archivu i materiálu obnovy přežije ztrátu vnitřní VM.
os.umask(0o077)
with tempfile.TemporaryDirectory(dir=directory) as tmp:
    work = Path(tmp)
    for name in ("pecet.cms", "obnova-podily.cms"):
        (work / name).write_bytes(subprocess.check_output(guest + ["cat", "/srv/polarita/data/bootstrap-test/openbao-test/" + name]))
    with subprocess.Popen(guest + ["cat", "/srv/polarita/backups/openbao/posledni.tar"], stdout=subprocess.PIPE) as source:
        with source.stdout:
            subprocess.run(["openssl", "cms", "-encrypt", "-stream", "-binary", "-aes-256-gcm",
                            "-outform", "DER", "-recip", str(directory / "test.crt"),
                            "-keyopt", "rsa_padding_mode:oaep", "-keyopt", "rsa_oaep_md:sha256",
                            "-out", str(work / "raft.cms")], stdin=source.stdout, check=True)
        if source.wait():
            raise RuntimeError("Přenos ověřené zálohy selhal")
    with subprocess.Popen(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
                           "-in", str(work / "raft.cms"), "-recip", str(directory / "test.crt"),
                           "-inkey", str(directory / "test.key")], stdout=subprocess.PIPE) as reader:
        with reader.stdout:
            copied = file_digest(reader.stdout, "sha256").hexdigest()
        if reader.wait() or copied != subprocess.check_output(guest + ["sha256sum", "/srv/polarita/backups/openbao/posledni.tar"]).decode().split()[0]:
            raise RuntimeError("Šifrovaný přenos archivu neprošel kontrolou")
    bundle = work / "obnova.tar"
    subprocess.run(["tar", "-cf", str(bundle), "-C", tmp, "pecet.cms", "obnova-podily.cms", "raft.cms"], check=True)
    bundle.replace(directory / "openbao-test-obnova.tar")
print("Šifrovaná sada obnovy je také na Ejpovicích.")
