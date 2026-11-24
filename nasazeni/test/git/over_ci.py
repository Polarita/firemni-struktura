"""Dokládá nativní CI pro skutečný zdrojový strom nasazované verze."""
import json
from pathlib import Path
import sys
import re
import socket
import subprocess
import time
from pripoj_identitu import DB, INSIDE

if socket.gethostname().split(".")[0] != "polarita-hq":
    raise SystemExit("Zkouška patří do testovací VM")
negative = "--odmitnuty-aigis" in sys.argv
candidate = json.loads(Path(sys.argv[1]).read_text())
branch, head, tree = (candidate[k] for k in ("branch", "commit", "tree"))
if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (tree,head)) or branch not in ("main","instalace/"+tree):
    raise RuntimeError("Neplatný identifikátor instalační revize")
git = INSIDE+["runuser","-u","gitea-test","--","git","--git-dir=/var/lib/gitea/git/spravce/firemni-struktura-test.git","rev-parse"]
def rev(ref):
    return subprocess.check_output(git+[ref],text=True).strip()

if rev("refs/heads/"+branch) != head or rev(head+"^{tree}") != tree:
    raise RuntimeError("Gitea nepotvrdila přesnou revizi a strom souborů")
if branch == "main":
    event = f"r.ref='refs/heads/main' and r.commit_sha='{head}' and r.event='push'"
else:
    number = subprocess.check_output(DB+[f"""select pr.index from pull_request pr join repository p on p.id=pr.head_repo_id
where p.id=pr.base_repo_id and p.owner_name='spravce' and p.lower_name='firemni-struktura-test'
and pr.head_branch='{branch}' and pr.base_branch='main' order by pr.index desc limit 1"""],text=True).strip()
    if not re.fullmatch(r"[1-9][0-9]*",number):
        raise RuntimeError("Chybí požadavek na ověření instalační větve")
    event = (f"r.ref in ('refs/pull/{number}/head','refs/pull/{number}/merge') and r.event='pull_request' "
             f"and (r.event_payload::jsonb #>> '{{pull_request,head,sha}}')='{head}' and not r.is_fork_pull_request")
query = f"""select r.id,r.status,r.commit_sha from action_run r join repository p on p.id=r.repo_id
where p.owner_name='spravce' and p.lower_name='firemni-struktura-test' and r.workflow_id='kontrola.yml'
and {event} order by r.id desc limit 1"""
previous = None
end = time.monotonic()+3000
while time.monotonic() < end:
    row = subprocess.check_output(DB+[query],text=True).strip()
    if previous != row:
        print("Gitea CI – běh a stav", row or "zatím nezařazen", flush=True)
        previous = row
    if row:
        run_id, status, checked = row.split("|")
        run, state = int(run_id), int(status)
        if not re.fullmatch(r"[0-9a-f]{40}", checked) or rev(checked+"^{tree}") != tree:
            raise RuntimeError("Workflow spustilo jiný strom než požadovaný archiv")
        if negative and state == 1:
            raise RuntimeError("CI přijalo kontrolní revizi s cyklem")
        if state == (2 if negative else 1):
            break
        if state not in (0,5,6,7,9):
            raise RuntimeError("Ověřovací workflow skončilo ve stavu "+str(state))
    time.sleep(5)
else:
    raise RuntimeError("Ověřovací workflow nedoběhlo v nastaveném limitu")
steps = subprocess.check_output(DB+[f"""select s.name,s.status from action_task_step s where s.task_id=(
select task_id from action_run_job where run_id={run} and job_id='kontrola' order by attempt desc limit 1)
order by s.index"""],text=True).splitlines()
required = ("Checkout","Python dependencies","Consistency check","AigisCode","S2 Eval Suite","S3 pricing kernel","S1 templates","Working tree","Remove the temporary")
if negative:
    # Odmítnutí musí pocházet ze stejného kroku i skutečného vzorku (pád runneru nestačí).
    from compression import zstd
    from io import BytesIO
    if (branch == "main" or len(steps) < 4 or not steps[3].startswith("AigisCode") or not steps[3].endswith("|2")
            or any(not step.startswith(name) or not step.endswith("|1") for step,name in zip(steps[:3],required[:3]))):
        raise RuntimeError("Nesouhlasí předešlé kroky nebo zdroj odmítnutí")
    filename = subprocess.check_output(DB+[f"""select t.log_filename from action_task t join action_run_job j
        on j.task_id=t.id where j.run_id={run} and j.job_id='kontrola' and t.log_in_storage
        order by j.attempt desc limit 1"""], text=True).strip()
    if not re.fullmatch(r"spravce/firemni-struktura-test/[0-9a-f]{2}/[0-9]+\.log\.zst", filename):
        raise RuntimeError("Chybí nativní uložený log odmítnuté úlohy")
    raw = subprocess.check_output(INSIDE+["cat", "/var/lib/gitea/data/actions_log/"+filename])
    with zstd.open(BytesIO(raw),"rt") as stream:
        if not any("Silný cyklus:" in line and "pol_aigis_prvni.py" in line and "pol_aigis_druhy.py" in line for line in stream):
            raise RuntimeError("Nativní log neobsahuje obě hrany zkoušeného cyklu")
    print(f"Gitea Actions odmítla revizi {head} v kroku AigisCode. Log úlohy {run} identifikoval oba soubory cyklu.")
    sys.exit(0)
if len(steps) != len(required) or any(not entry.startswith(name) or not entry.endswith("|1") for entry,name in zip(steps,required)):
    raise RuntimeError("Gitea nepotvrdila všechny kroky zkoušky")
print(f"Gitea Actions potvrdila všech {len(steps)} kroků pro větev {branch}, revizi {checked} a strom {tree}.")
