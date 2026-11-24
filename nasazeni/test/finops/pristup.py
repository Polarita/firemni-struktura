"""Místní identity pro čtení, volání, návrh CEO a technické uvolnění. Přístup pouze přes unixový socket."""
import os
from pathlib import Path
import pwd
import socket
import subprocess
import tempfile

if os.geteuid() or socket.gethostname().split(".")[0] != "postgres-test":
    raise SystemExit("Identity FinOps patří do postgres-test")
roles = ["pol_finops_read", "pol_finops_call", "pol_finops_propose", "pol_finops_release"]
for role in roles:
    try:
        entry = pwd.getpwnam(role)
    except KeyError:
        subprocess.run(["useradd","--system","--no-create-home","--shell","/usr/sbin/nologin",role],check=True)
    else:
        if entry.pw_uid == 0 or entry.pw_shell != "/usr/sbin/nologin":
            raise RuntimeError("Neočekávaná identita služby " + role)
file = Path("/etc/polarita-postgres/pg_hba.conf")
lines = file.read_text().splitlines()
rules = ["local db_paperclip " + role + " peer" for role in roles]
wanted = [line for line in lines if line not in rules]
i = wanted.index("local all postgres peer") + 1
wanted[i:i] = rules
if wanted != lines:
    with tempfile.NamedTemporaryFile("w", dir=file.parent, delete=False) as f:
        f.write("\n".join(wanted)+"\n")
        os.fchmod(f.fileno(), file.stat().st_mode & 0o777)
    os.replace(f.name,file)
subprocess.run(["systemctl","reload","polarita-postgres.service"],check=True)
