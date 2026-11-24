"""Uchová klientské heslo HTTP a nezávislé heslo Restic v TEST obálkách TPM."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile

ROOT = Path("/srv/polarita/data/bootstrap-test/restic-test")
REPO = "rest:https://10.239.33.15:8443/polarita-test/firma/"
CA = "/srv/polarita/infra/restic-test/server.crt"


def credential(name):
    if socket.gethostname().split(".")[0] != "polarita-hq" or os.geteuid():
        raise RuntimeError("Správa přístupu patří do testovací VM")
    dest = ROOT/(name+".cred")
    return subprocess.check_output(["systemd-creds","decrypt","--name="+name,str(dest),"-"]).decode()


def initialize():
    import bcrypt
    os.umask(0o077)
    ROOT.mkdir(exist_ok=True,mode=0o700)
    if subprocess.check_output(["findmnt","-n","-o","SOURCE","-T",str(ROOT)],text=True).strip()!="polarita_zfs/data/bootstrap-test":
        raise RuntimeError("Chybí šifrovaný dataset TEST")
    for name in ("restic-http","restic-repozitar"):
        dest=ROOT/(name+".cred")
        if not dest.exists():
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                stage=Path(tmp)/name
                subprocess.run(["systemd-creds","encrypt","--with-key=tpm2","--tpm2-pcrs=7",
                                "--name="+name,"-",str(stage)],input=secrets.token_urlsafe(40).encode(),check=True)
                stage.chmod(0o600)
                os.link(stage,dest)
    stored=bcrypt.hashpw(credential("restic-http").encode(),bcrypt.gensalt(rounds=10))
    subprocess.run(["incus","exec","-T","restic-test","--","sh","-ec",
                    "umask 077; cd /etc/polarita-restic; cat >.htpasswd-next; chgrp pol-restic .htpasswd-next; chmod 0640 .htpasswd-next"],input=b"polarita-test:"+stored+b"\n",check=True)
    subprocess.run(["incus","exec","-T","restic-test","--","mv","-T","/etc/polarita-restic/.htpasswd-next",
                    "/etc/polarita-restic/htpasswd"],check=True)


if __name__=="__main__":
    initialize()
