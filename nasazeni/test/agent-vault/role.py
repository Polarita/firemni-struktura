"""Samostatné místní identity agentů. CEO ve stavu SHADOW pouze čte."""
import grp
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile

def main(source):
    agents = json.loads((source/"nastroje/kanon.json").read_text())["agents"]
    if len(agents)!=20 or len({a["id"] for a in agents})!=20 or not all(re.fullmatch(r"1[1-8]\d{3}",a["id"]) for a in agents):
        raise ValueError("Neplatný registr rolí")
    for group in ("pol-vault-cteni","pol-vault-zapis"):
        try:
            grp.getgrnam(group)
        except KeyError:
            subprocess.run(["groupadd","--system",group],check=True)
    for agent in agents:
        user = "pol-vault-"+agent["id"]
        try:
            account = pwd.getpwnam(user)
        except KeyError:
            subprocess.run(["useradd","--system","--no-create-home","--home-dir","/nonexistent",
                            "--shell","/usr/sbin/nologin","-g","pol-vault-cteni",user],check=True)
            account = pwd.getpwnam(user)
        if account.pw_gid!=grp.getgrnam("pol-vault-cteni").gr_gid or account.pw_shell!="/usr/sbin/nologin":
            raise RuntimeError("Existující identita neodpovídá znalostní roli")
        writes = grp.getgrnam("pol-vault-zapis").gr_gid in os.getgrouplist(user,account.pw_gid)
        if agent["id"] == "11001" and writes:
            subprocess.run(["gpasswd","-d",user,"pol-vault-zapis"],check=True)
        elif agent["id"]!="11001" and not writes:
            subprocess.run(["usermod","-aG","pol-vault-zapis",user],check=True)
    cmd = "/usr/local/sbin/agent_vault"
    policy = ("%pol-vault-cteni ALL=(root) NOPASSWD: "+", ".join(cmd+" "+op for op in ("get-context","get-context *","search *"))
              +"\n%pol-vault-zapis ALL=(root) NOPASSWD: "+cmd+" log *, "+cmd+" adr *\n")
    dst = Path("/etc/sudoers.d/polarita-agent-vault")
    with tempfile.NamedTemporaryFile("w",dir=dst.parent,prefix=".agent-vault-",delete=False) as f:
        pending = Path(f.name)
        f.write(policy)
        os.fchmod(f.fileno(),0o440)
    try:
        subprocess.run(["visudo","-cf",pending],check=True)
        os.replace(pending,dst)
    finally:
        pending.unlink(missing_ok=True)

if __name__=="__main__":
    main(Path(sys.argv[1]))
