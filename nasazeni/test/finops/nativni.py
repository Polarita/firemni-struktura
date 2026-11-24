"""Uloží vzorový návrh a jeho rozhodnutí přes tři oddělené místní identity."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID, uuid5

def db(role, statement, **variables):
    args = ["incus","exec","-T","postgres-test","--","runuser","-u","pol_finops_"+role,
            "--","psql","-XqAtw","-v","ON_ERROR_STOP=1","-d","db_paperclip"]
    for key, value in variables.items():
        args.extend(["-v",key+"="+str(value)])
    return subprocess.check_output(args,input=statement,text=True).strip()

def main():
    if os.geteuid() or socket.gethostname().split(".")[0]!="polarita-hq":
        raise SystemExit("FinOps TEST vyžaduje polarita-hq")
    root = Path(__file__).resolve().parent
    status = json.loads(db("read","SELECT polarita_finops.stav()"))
    month = status["mesic"]
    namespace = UUID("a1ae63c9-5c87-4e98-bafd-bba1de4b7eb8")
    scope = dict(navrh=str(uuid5(namespace,"návrh/"+month)),ukol=str(uuid5(namespace,"úkol/"+month)),
                 pozice="16002",centy=1,mesic=month,rezim="TEST")
    db("propose","SELECT polarita_finops.navrh(:'navrh',:'pozice',:'ukol',:centy)",**scope)
    subprocess.run(["incus","file","push","--mode","0644",root/"hlas.py",
                    "paperclip-test/etc/polarita-paperclip/finops-hlas.py"],check=True)
    with Path("/srv/polarita/data/bootstrap-test/test-login/heslo").open("rb") as secret:
        raw=subprocess.check_output(["incus","exec","-T","paperclip-test","--","python3",
                    "/etc/polarita-paperclip/finops-hlas.py",sys.argv[1],json.dumps(scope)],stdin=secret,text=True)
    approval=str(UUID(raw.strip()))
    db("release","SELECT polarita_finops.uvolni(:'hlas',:'navrh',:'pozice',:'ukol',:centy)",hlas=approval,**scope)
    print("Rozhodnutí",approval,"potvrdil správce v Paperclipu. Návrh zapsala identita 11001 a jediný cent pro vzorovou úlohu pozice 16002 uvolnila oddělená identita 17005. Výdaj nevznikl.")

if __name__=="__main__":
    main()
