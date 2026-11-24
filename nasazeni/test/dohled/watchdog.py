"""Samostatné sledování signálu z VM a kontroly Checkmk na odděleném záložním cíli."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import sys
import time

BASE=Path("/var/lib/polarita-watchdog")


def replace(path,record):
    temp=path.with_suffix(".next")
    temp.write_text(json.dumps(record,ensure_ascii=False)+"\n")
    temp.replace(path)


def update(base):
    now=int(time.time())
    heartbeat=base/"signal.json"
    data=json.loads(heartbeat.read_bytes()) if heartbeat.is_file() else {}
    states={}
    for key in ("polarita-hq","checkmk"):
        age=now-data.get(key,0)
        states[key]="OK" if 0<=age<240 else "CRITICAL"
    last=base/"stav.json"
    prior=json.loads(last.read_bytes()) if last.is_file() else {}
    for key,state in states.items():
        if state != prior.get(key):
            with (base/"udalosti.jsonl").open("a") as log:
                log.write(json.dumps({"utc":datetime.now(timezone.utc).isoformat(),"sluzba":key,"stav":state})+"\n")
    replace(last,states)
    return states


if __name__=="__main__":
    if socket.gethostname().split(".")[0]!="restic-test":
        raise SystemExit("Watchdog potřebuje oddělený záložní cíl TEST")
    os.umask(0o077)
    if sys.argv[1:]==["--prijem"]:
        incoming=json.load(sys.stdin)
        if set(incoming)!={"polarita-hq","checkmk"} or any(type(v) is not int or v<0 for v in incoming.values()):
            raise ValueError("Chybný signál dohledu")
        replace(BASE/"signal.json",incoming)
    elif not sys.argv[1:]:
        update(BASE)
    elif sys.argv[1:]==["--zkouska"]:
        from tempfile import TemporaryDirectory
        now=int(time.time())
        with TemporaryDirectory(dir=BASE) as stage:
            base=Path(stage)
            for hq,cmk in [(now,now),(now,now-300),(now-300,now-300),(now,now)]:
                replace(base/"signal.json",{"polarita-hq":hq,"checkmk":cmk})
                update(base)
            events=[json.loads(line) for line in (base/"udalosti.jsonl").read_text().splitlines()]
            for name in ("polarita-hq","checkmk"):
                if [e["stav"] for e in events if e["sluzba"]==name]!=["OK","CRITICAL","OK"]:
                    raise RuntimeError("Chybí upozornění na výpadek či zotavení")
        print("Samostatný watchdog zaznamenal výpadek Checkmk i signálu hostitele a oba návraty do provozu.")
    else:
        raise SystemExit("Neplatný příkaz")
