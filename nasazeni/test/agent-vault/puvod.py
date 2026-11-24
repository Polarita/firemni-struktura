"""Porovná zdroje běžícího CLI s objekty verze v místní Gitea."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

def verify(dest):
    marker = dest/"revize-ci.json"
    if not marker.is_file():
        subprocess.run([sys.executable,dest/"nasazeni/test/git/zdroj_ci.py",dest/"zdroj-ci.tar.gz"],check=True)
    data = json.loads(marker.read_bytes())
    rev,tree,branch = (data[k] for k in ("commit","tree","branch"))
    if not all(re.fullmatch("[0-9a-f]{40}",s) for s in (rev,tree)) or branch not in ("main","instalace/"+tree):
        raise ValueError("Neplatná místní zdrojová revize")
    git=["incus","exec","-T","gitea-test","--","runuser","-u","gitea-test","--","git",
         "--git-dir=/var/lib/gitea/git/spravce/firemni-struktura-test.git"]
    if subprocess.check_output(git+["rev-parse","refs/heads/"+branch,rev+"^{tree}"],text=True).splitlines()!=[rev,tree]:
        raise ValueError("Zdrojová větev nebo strom se změnily")
    prefix="nasazeni/test/agent-vault/"
    entries=subprocess.check_output(git+["ls-tree","-rz",rev,"--",prefix,"nasazeni/test/zaklad/uv.sh"]).split(b"\0")
    checked=set()
    for entry in filter(None,entries):
        meta,name=entry.split(b"\t",1)
        mode,kind,oid=meta.split()
        name=name.decode()
        if mode not in (b"100644",b"100755") or kind!=b"blob" or (not name.startswith(prefix) and name!="nasazeni/test/zaklad/uv.sh"):
            raise ValueError("Neočekávaný objekt ve zdrojích")
        file=dest/name
        content=file.read_bytes()
        if hashlib.sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()!=oid.decode():
            raise ValueError("Nasazovaný soubor neodpovídá verzi v Gitea")
        checked.add(name)
    expected = {prefix+p.name for p in (dest/prefix).iterdir() if p.is_file()} | {"nasazeni/test/zaklad/uv.sh"}
    if checked!=expected or prefix+"cli.py" not in checked:
        raise ValueError("Gitea neobsahuje úplný zdrojový strom CLI")
    return rev

if __name__=="__main__":
    commit=verify(Path(sys.argv[1]).resolve())
    print("Firemní Gitea potvrdila všechny distribuované soubory agent_vault v revizi "+commit+".")
