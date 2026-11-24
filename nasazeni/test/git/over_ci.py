"""Dokládá kompletní nativní běh Actions pro skutečný HEAD soukromé větve main."""
import re
import socket
import subprocess
import time
from pripoj_identitu import DB, INSIDE

if socket.gethostname().split(".")[0] != "polarita-hq":
    raise SystemExit("Zkouška patří do testovací VM")
head = subprocess.check_output(INSIDE+["runuser","-u","gitea-test","--","git",
                  "--git-dir=/var/lib/gitea/git/spravce/firemni-struktura-test.git","rev-parse","refs/heads/main"],text=True).strip()
if not re.fullmatch(r"[0-9a-f]{40,64}",head):
    raise RuntimeError("Neznámá revize soukromého repozitáře")
query = f"""select r.id,r.status from action_run r join repository p on p.id=r.repo_id
where p.owner_name='spravce' and p.lower_name='firemni-struktura-test' and r.workflow_id='kontrola.yml'
and r.ref='refs/heads/main' and r.commit_sha='{head}' order by r.id desc limit 1"""
previous = None
end = time.monotonic()+3000
while time.monotonic() < end:
    row = subprocess.check_output(DB+[query],text=True).strip()
    if previous != row:
        print("Gitea CI – běh a stav", row or "zatím nezařazen", flush=True)
        previous = row
    if row:
        run,state = map(int,row.split("|"))
        if state == 1:
            break
        if state not in (0,5,6,7,9):
            raise RuntimeError("Ověřovací workflow skončilo ve stavu "+str(state))
    time.sleep(5)
else:
    raise RuntimeError("Ověřovací workflow nedoběhlo v nastaveném limitu")
steps = subprocess.check_output(DB+[f"""select s.name,s.status from action_task_step s where s.task_id=(
select task_id from action_run_job where run_id={run} and job_id='kontrola' order by attempt desc limit 1)
order by s.index"""],text=True).splitlines()
required = ("Checkout","Python dependencies","Consistency check","S2 Eval Suite","S3 pricing kernel","S1 templates","Working tree","Remove the temporary")
if len(steps) != len(required) or any(not entry.startswith(name) or not entry.endswith("|1") for entry,name in zip(steps,required)):
    raise RuntimeError("Gitea nepotvrdila všechny kroky zkoušky")
print(f"Gitea Actions potvrdila všech {len(steps)} kroků pro revizi {head}.")
