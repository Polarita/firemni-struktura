"""Z původního PDF a potvrzení Decisions zapíše protokol a termín bez osobních údajů v ERP."""
import base64
from datetime import date, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
from uuid import UUID, NAMESPACE_URL, uuid5

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC.parent / "trezor"))
import pristupy as bao

PROOF = Path("/srv/polarita/workspace/dukazy/blok-09")
GUEST = ["incus", "exec", "-T", "postgres-test", "--"]


def encryption_key():
    bao.HTTP = bao.build_opener(bao.ProxyHandler({}), bao.HTTPSHandler(
        context=ssl.create_default_context(cafile=str(bao.WORK / "ca.crt"))))
    manager = bao.login(bao.recover("bao-sprava"))
    try:
        bao.initialize_protocol_key(manager)
        bridge = bao.login(bao.credentials("compliance-bridge-test", manager))
    finally:
        bao.request("POST", "auth/token/revoke-self", {}, manager)
    try:
        key = bao.request("GET", "test/data/akademie/protokol", token=bridge)["data"]["data"]["klic"]
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("OpenBao nevydal klíč protokolů TEST.")
        bao.expect_forbidden("GET", "test/data/databaze/db_gdpr_zkousky", bridge)
        return key.encode()
    finally:
        bao.request("POST", "auth/token/revoke-self", {}, bridge)


def crypt(home, key, content, args):
    with tempfile.TemporaryFile(dir="/dev/shm") as secret:
        secret.write(key + b"\n")
        secret.seek(0)
        command = ["gpg", "--homedir", home, "--batch", "--quiet", "--no-symkey-cache", "--pinentry-mode", "loopback",
                   "--passphrase-fd", str(secret.fileno()), "--output", "-", *args]
        return subprocess.check_output(command, input=content, pass_fds=(secret.fileno(),), timeout=120)


def write_db(database, payload):
    command = [*GUEST, "python3", "/etc/polarita-postgres/akademie-evidence.py", database]
    return json.loads(subprocess.check_output(command, input=json.dumps(payload).encode(), timeout=160))


def register():
    record = json.loads((PROOF / "akademie-komise.json").read_text())
    decision = json.loads((PROOF / "akademie-rozhodnuti.json").read_text())
    issue = record["vydani"]
    if (not re.fullmatch(r"[0-9a-f]{64}", issue) or record["rezim"] != "TEST" or decision["rezim"] != "TEST"
            or decision["stav"] != "approved" or decision["vydani"] != issue or record["osoba"] != "test-akademie-a"
            or record["komise"] != ["TEST-PREDS-1001", "TEST-CLEN-02", "TEST-CLEN-03"]
            or record["druh"] != "elektrotechnik" or record["procent"] != 100):
        raise ValueError("Podklady pro zápis do evidence se liší od potvrzené cvičné zkoušky.")
    pdf = (PROOF / f"akademie-komise-{issue}.pdf").read_bytes()
    if not pdf.startswith(b"%PDF-") or hashlib.sha256(pdf).hexdigest() != record["protokol_sha256"]:
        raise ValueError("Předané PDF neodpovídá zapečetěnému protokolu.")
    ident = str(uuid5(NAMESPACE_URL, "urn:polarita:test:akademie:vydani:" + issue))
    dates = {"id": ident, "provedeno": datetime.fromisoformat(record["provedeno"]).isoformat(),
             "do": date.fromisoformat(record["platnost_do"]).isoformat()}
    if not re.fullmatch(r"POL-[0-9]+", decision["identifier"]):
        raise ValueError("Spis má neplatné číslo.")
    deadline = dict(dates, spis=decision["identifier"], rozhodnuti=str(UUID(decision["approval"])))
    def person(name):
        return str(uuid5(NAMESPACE_URL, "urn:polarita:test:akademie:osoba:" + name))

    # Do databáze vstupuje pouze šifrované PDF. Klíč neopustí hlavní VM.
    if not all(shutil.which(program) for program in ("gpg", "gpg-agent", "gpgconf")):
        subprocess.run(["apt-get", "-o", "DPkg::Lock::Timeout=300", "-y", "--no-install-recommends",
                        "install", "gpg", "gpg-agent", "gpgconf"], check=True,
                       env=dict(os.environ, DEBIAN_FRONTEND="noninteractive"))
    key = encryption_key()
    cmd = "/etc/polarita-postgres/akademie-evidence.py"
    subprocess.run(["incus", "file", "push", "--mode=0644", str(SRC / "evidence_db.py"), "postgres-test" + cmd + ".next"], check=True)
    subprocess.run([*GUEST, "mv", "-T", cmd + ".next", cmd], check=True)
    with tempfile.TemporaryDirectory(dir="/dev/shm") as home:
        try:
            encrypted = crypt(home, key, pdf, ["--cipher-algo", "AES256", "--symmetric"])
            stored = write_db("db_gdpr_zkousky", dict(dates, osoba=person(record["osoba"]),
                komise=[person(name) for name in record["komise"]], otisk=record["protokol_sha256"],
                sifra=base64.b64encode(encrypted).decode()))
            if crypt(home, key, base64.b64decode("".join(stored.split()), validate=True), ["--decrypt"]) != pdf:
                raise ValueError("Dešifrované PDF z db_gdpr_zkousky se liší od ověřeného archivu.")
        finally:
            subprocess.run(["gpgconf", "--homedir", home, "--kill", "gpg-agent"], check=True)
    if write_db("db_erp_lhutnik", deadline) != dates["do"]:
        raise ValueError("Centrální lhůtník nepotvrdil správné datum.")
    print(f"Spis {deadline['spis']} má v Centrálním lhůtníku termín {dates['do']}. "
          "Po načtení a dešifrování z db_gdpr_zkousky odpovídá celý protokol PDF v archivu.")


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        sys.exit("Evidence patří do firemní VM v TEST.")
    with open("/run/polarita-akademie-vydani.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        register()
