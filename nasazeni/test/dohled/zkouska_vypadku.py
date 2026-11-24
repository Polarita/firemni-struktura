"""Očekává skutečné přechody Checkmk po zastavení a obnovení jediné zkušební služby."""
import json
import socket
import subprocess
import time

TEST="Polarita Zkusebni sluzba"
UNIT="polarita-dohled-vzorek.socket"
TARGET="checkmk-test"


def run(*cmd,**kwargs):
    return subprocess.run(cmd,check=True,capture_output=True,timeout=50,**kwargs).stdout


def inside(*cmd):
    return run("incus","exec","-T",TARGET,"--",*cmd)


def events():
    path="/var/lib/polarita-alert-test/udalosti.jsonl"
    probe=subprocess.run(["incus","exec","-T",TARGET,"--","test","-f",path])
    if probe.returncode==1:
        return []
    probe.check_returncode()
    return [json.loads(line) for line in inside("cat",path).splitlines()]


def wait_state(expected, *, stable=False):
    since=int(time.time())
    deadline=time.monotonic()+(420 if stable else 240)
    while time.monotonic()<deadline:
        now=int(time.time())
        # Pasivní lokální kontroly vyhodnotí skutečný Check_MK aktivní sběr.
        command=f"[{now}] SCHEDULE_FORCED_SVC_CHECK;polarita-hq;Check_MK;{now}\n"
        run("incus","exec","-T",TARGET,"--","runuser","-u","polarita","--","sh","-c",
            'pipe=/omd/sites/polarita/tmp/run/nagios.cmd; test -p "$pipe" && cat >"$pipe"',input=command.encode())
        time.sleep(5)
        table=json.loads(inside("runuser","-u","polarita","--","python3","/usr/local/lib/polarita-dohled/livestatus.py"))
        row=table.get(TEST,{})
        if stable and (row.get("kolisa") != 0 or row.get("zmeny_pct") != 0):
            continue
        if row.get("stav")==expected and row.get("typ")==1 and row.get("cas",0)>=since:
            return
    raise RuntimeError("Checkmk včas nepotvrdil stav služby "+str(expected))


def wait_delivery(start,wanted):
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        channels={x["kanal"] for x in events()[start:] if x["sluzba"]==TEST and x["stav"]==wanted}
        if channels=={"smtp","telegram-test"}:
            return
        time.sleep(3)
    raise RuntimeError("Neúplné doručení události "+wanted+" místním kanálům")


def main():
    if socket.gethostname().split(".")[0]!="polarita-hq":
        raise SystemExit("Zkouška musí běžet uvnitř ředitelství")
    run("systemctl","start",UNIT)
    run("systemctl","start","polarita-dohled-sber.service")
    # Před dalším výpadkem necháme odeznít historii předchozí zkoušky.
    wait_state(0, stable=True)
    start=len(events())
    try:
        run("systemctl","stop",UNIT)
        run("systemctl","start","polarita-dohled-sber.service")
        wait_state(2)
        wait_delivery(start,"CRITICAL")
    finally:
        run("systemctl","start",UNIT)
        run("systemctl","start","polarita-dohled-sber.service")
    wait_state(0)
    wait_delivery(start,"OK")
    print("Checkmk zachytil skutečný výpadek a obnovení zkušební služby. Obě události dorazily zvlášť po SMTP a na místní testovací rozhraní Telegramu.")


if __name__=="__main__":
    main()
