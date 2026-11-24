"""Zapíše jednorázový CI účet pouze pro soukromý testovací repozitář."""
import fcntl
from pathlib import Path
import re
import socket
import subprocess
import sys
from pripoj_identitu import CLI, DB
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
    if "--cekajici" in sys.argv:
        pending = subprocess.check_output(DB + ["""select exists(select 1 from action_run_job j
            join repository r on r.id=j.repo_id where j.status=5 and r.owner_name='spravce'
            and r.lower_name='firemni-struktura-test')"""]).strip()
        if pending == b"f":
            sys.exit(0)
        if pending != b"t":
            raise RuntimeError("Nelze určit stav pracovní fronty")
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
               "sh","-ec",'IFS= read -r GITEA_RUNNER_REGISTRATION_TOKEN; export GITEA_RUNNER_REGISTRATION_TOKEN; exec "$@"',"registrace",
               "/opt/polarita-runner/runner","--config","/etc/polarita-gitea/runner.yaml","register",
               "--no-interactive","--ephemeral","--name","polarita-ci-test","--labels","polarita-incus:host",
               "--instance",url]
        res = subprocess.run(inside+cmd,input=token+b"\n",capture_output=True)
        if res.returncode:
            detail = (res.stderr + res.stdout).replace(token,b"[skryto]").decode(errors="replace")
            detail = re.sub(r"[A-Za-z0-9_+/=-]{24,}", "[skryto]", detail)
            raise RuntimeError(f"Registrace pracovníka selhala s kódem {res.returncode}: {detail[-700:]}")
        subprocess.run(inside+["systemctl","start","gitea-ci.service"],check=True)
        subprocess.run(inside+["systemctl","is-active","--quiet","gitea-ci.service"],check=True)
        print("Jednorázový pracovník je registrovaný pouze pro "+scope+".")
