"""Testovací obálka přístupu k záloze pro ztrátu původního vTPM. Data nikdy nejdou do aplikačních logů."""
import base64
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory

from pristup import CA, REPO, credential


def check(info,certificate):
    if info["repo"]!=REPO:
        raise ValueError("Neznámý cíl obnovy TEST")
    env={**os.environ,"RESTIC_REPOSITORY":REPO,"RESTIC_REST_USERNAME":"polarita-test",
         "RESTIC_REST_PASSWORD":info["http"],"RESTIC_PASSWORD":info["klic"],"GOMAXPROCS":"1"}
    config=json.loads(subprocess.check_output(["restic","--no-cache","--cacert",str(certificate),"cat","config"],env=env))
    if not re.fullmatch("[a-f0-9]{64}",config["id"]):
        raise RuntimeError("Repozitář nevrátil platnou identitu")
    return config["id"]


def create():
    os.umask(0o077)
    info={"repo":REPO,"http":credential("restic-http"),"klic":credential("restic-repozitar"),
          "ca":base64.b64encode(Path(CA).read_bytes()).decode()}
    info["id"]=check(info,CA)
    recipient="/srv/polarita/infra/openbao-test/test-obnova.crt"
    envelope=subprocess.check_output(["openssl","cms","-encrypt","-binary","-aes-256-gcm","-outform","DER",
                                     "-recip",recipient,"-keyopt","rsa_padding_mode:oaep","-keyopt","rsa_oaep_md:sha256"],
                                    input=json.dumps(info).encode())
    # Cíl je v oddělené záložní instanci. Přes veřejné rozhraní Restic se obálka nevydává.
    subprocess.run(["incus","exec","-T","restic-test","--","sh","-ec",
                    'set -eu; umask 077; mountpoint -q /var/lib/restic-test; install -d -m 0700 /var/lib/restic-test/obnova; cd /var/lib/restic-test/obnova; cat >pristup.next; mv -T pristup.next pristup.cms'],
                   input=envelope,check=True)


def verify():
    info=json.load(sys.stdin)
    with TemporaryDirectory(dir="/run") as tmp:
        certificate=Path(tmp)/"restic.crt"
        certificate.write_bytes(base64.b64decode(info["ca"],validate=True))
        if check(info,certificate)!=info["id"]:
            raise RuntimeError("Obálka otevřela jiný repozitář")
    print("Údaje z obnovovací obálky otevřely původní šifrovaný repozitář bez použití vTPM pro přihlášení.")


if __name__=="__main__":
    if socket.gethostname().split(".")[0]!="polarita-hq" or os.geteuid():
        raise SystemExit("Obálka je určena pro testovací ředitelství")
    if sys.argv[1:]==["--vytvor"]:
        create()
    elif sys.argv[1:]==["--over"]:
        verify()
    else:
        raise SystemExit("Neplatný příkaz")
