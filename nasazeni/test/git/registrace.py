"""Zapíše jednorázový CI účet pouze pro soukromý testovací repozitář."""
import fcntl
from pathlib import Path
import socket
import subprocess
from pripoj_identitu import CLI
from repozitar import OWNER, REPO

if socket.gethostname().split(".")[0] != "polarita-hq":
    raise SystemExit("Registrace patří do testovací VM")
vm = "gitea-runner-test"
inside = ["incus","exec","-T",vm,"--"]
root = Path(__file__).resolve().parent
scope = f"{OWNER}/{REPO}"
url = subprocess.check_output(["incus","exec","-T","gitea-test","--","cat","/etc/polarita-gitea/url"],text=True).strip()
with Path("/run/polarita-gitea-registrace.lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    for name, path in (("runner.yaml","/etc/polarita-gitea/"),("gitea-ci.service","/etc/systemd/system/")):
        subprocess.run(["incus","file","push","--mode=0644",str(root/name), vm+path],check=True)
    subprocess.run(inside+["install","-d","-m","0700","-o","pol-ci","-g","pol-ci",
                           "/var/lib/polarita-ci/registrace","/var/lib/polarita-ci/ulohy"],check=True)
    subprocess.run(inside+["systemctl","daemon-reload"],check=True)
    if subprocess.run(inside+["systemctl","is-active","--quiet","gitea-ci.service"]).returncode == 0:
        print("Jednorázový pracovník CI již běží.")
    else:
        token = subprocess.check_output(CLI+["actions","generate-runner-token","--scope",scope]).strip()
        if not (16 <= len(token) <= 160) or any(x < 33 or x > 126 for x in token):
            raise RuntimeError("Gitea nevydala registrační token repozitáře")
        cmd = ["runuser","-u","pol-ci","--","env","HOME=/var/lib/polarita-ci","SSL_CERT_FILE=/etc/polarita-gitea/git-ca.crt",
               "/opt/polarita-runner/runner","--config","/etc/polarita-gitea/runner.yaml","register",
               "--no-interactive","--ephemeral","--name","polarita-ci-test","--labels","polarita-incus:host",
               "--instance",url,"--token-file","/dev/stdin"]
        res = subprocess.run(inside+cmd,input=token+b"\n",capture_output=True)
        if res.returncode:
            raise RuntimeError(f"Registrace pracovníka selhala s kódem {res.returncode}")
        subprocess.run(inside+["systemctl","start","gitea-ci.service"],check=True)
        subprocess.run(inside+["systemctl","is-active","--quiet","gitea-ci.service"],check=True)
        print("Jednorázový pracovník je registrovaný pouze pro "+scope+".")
