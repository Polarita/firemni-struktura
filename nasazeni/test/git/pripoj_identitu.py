"""Připojí jediný klient Gitea přes místní rozhraní Keycloaku a Gitea."""
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "identita"))
from sprava_klientu import MANAGER, REALM, api, find_client, manager_token, secret

ADMIN = "polarita-sprava-gitu"
STORE = Path("/srv/polarita/data/bootstrap-test/gitea-sprava")
INSIDE = ["incus", "exec", "-T", "gitea-test", "--"]
CLI = INSIDE + ["runuser", "-u", "gitea-test", "--", "env", "HOME=/var/lib/gitea/home",
                "GITEA_WORK_DIR=/var/lib/gitea/data", "/opt/gitea/gitea-28.4.0-linux-amd64",
                "--config", "/run/polarita-gitea/app.ini"]
DB = ["incus","exec","-T","postgres-test","--","runuser","-u","postgres","--","psql",
      "-XAt","-v","ON_ERROR_STOP=1","-d","gitea","-c"]


def admin_password():
    path = STORE / "gitea-sprava.cred"
    pending = STORE / "prvni-vytvoreni"
    row = subprocess.check_output(DB + [f"""SELECT is_admin FROM "user" WHERE lower_name='{ADMIN}'"""]).strip()
    if row not in (b"", b"t"):
        raise RuntimeError("Kolize jména služebního správce Gitu")
    if not row:
        if path.exists():
            raise RuntimeError("Chybí zavedený správce v databázi Gitu")
        with pending.open("wb") as out:
            subprocess.run(CLI + ["admin","user","create","--username",ADMIN,"--email",ADMIN+"@polarita.test",
                                  "--admin","--random-password","--random-password-length","40",
                                  "--must-change-password=false"],stdout=out,check=True)
            out.flush()
            os.fsync(out.fileno())
    if not path.exists():
        match = re.search(rb"(?m)^generated random password is '([^\r\n]{40})'\r?$", pending.read_bytes())
        if not match:
            raise RuntimeError("Chybí výsledek vytvoření účtu Gitea")
        stage = path.with_suffix(".next")
        subprocess.run(["systemd-creds","encrypt","--with-key=tpm2","--tpm2-pcrs=7",
                        "--name=gitea-sprava","-",str(stage)],input=match[1],check=True)
        stage.replace(path)
    password = subprocess.check_output(["systemd-creds","decrypt","--name=gitea-sprava",str(path),"-"]).decode()
    pending.unlink(missing_ok=True)
    return password


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Příprava patří do testovací VM")
    os.umask(0o077)
    STORE.mkdir(mode=0o700, exist_ok=True)
    if subprocess.check_output(["findmnt","-n","-o","SOURCE","-T",str(STORE)],text=True).strip() != "polarita_zfs/data/bootstrap-test":
        raise RuntimeError("Chybí šifrované TEST úložiště")
    if "--lokalne" not in sys.argv:
        pid = json.loads(subprocess.check_output(["incus","query","/1.0/instances/keycloak-test/state"]))["pid"]
        os.execvp("nsenter", ["nsenter","--target",str(pid),"--net","--",sys.executable,__file__,"--lokalne"])
    with (STORE / ".sprava").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        public = subprocess.check_output(INSIDE+["cat","/etc/polarita-gitea/url"],text=True).strip()
        u = urlsplit(public)
        if u.scheme != "https" or u.path != "/git/" or not re.fullmatch("[a-z0-9.-]+",u.netloc):
            raise RuntimeError("Neočekávaná adresa Gitea")
        origin = "https://"+u.netloc
        password = admin_password()
        token = manager_token(secret(MANAGER))
        client = find_client("gitea",token)
        if not client or client["protocol"] != "openid-connect":
            raise RuntimeError("Chybí klient Gitea v testovacím realmu")
        path = REALM+"/clients/"+client["id"]
        settings = {"enabled":True,"publicClient":False,"standardFlowEnabled":True,"implicitFlowEnabled":False,
                    "directAccessGrantsEnabled":False,"serviceAccountsEnabled":False,"clientAuthenticatorType":"client-secret",
                    "redirectUris":[public+"user/oauth2/keycloak/callback"],"webOrigins":[origin]}
        if any(client.get(k)!=v for k,v in settings.items()):
            api("PUT",path,token,{**client,**settings})
        verified = find_client("gitea",token)
        if any(verified.get(k)!=v for k,v in settings.items()):
            raise RuntimeError("Keycloak nepotvrdil nastavení klienta Gitea")
        value = api("GET",path+"/client-secret",token)["value"]
        if not value:
            raise RuntimeError("Chybí důvěrný klientský klíč")
        source = Path(__file__).with_name("zdroj_prihlaseni.py")
        subprocess.run(["incus","file","push","--mode=0644",str(source),"gitea-test/etc/polarita-gitea/"],check=True)
        data = {"admin":ADMIN,"password":password,"key":value,"origin":origin}
        subprocess.run(INSIDE+["python3","/etc/polarita-gitea/zdroj_prihlaseni.py"],
                       input=json.dumps(data).encode(),check=True)
    print("Gitea má aktivní přihlášení přes důvěrného klienta Keycloaku s přesnou návratovou adresou.")


if __name__ == "__main__":
    main()
