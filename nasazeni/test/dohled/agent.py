"""Rozhraní Checkmk local checks omezené na čtení stavu z hostitelské VM."""
import json
from pathlib import Path
import time

record=json.loads(Path("/var/lib/polarita-dohled/stav.json").read_bytes())
age=int(time.time())-record["cas"]
print("<<<check_mk>>>\nVersion: polarita-test-1\nAgentOS: linux\nHostname: polarita-hq\n<<<local>>>")
print(f'{0 if 0<=age<180 else 2} "Polarita aktualnost sond" age={age}s Měření je staré {age} sekund')
for name,(status,metrics,summary) in sorted(record["sluzby"].items()):
    if age>=180 or age<0:
        status,metrics,summary=3,"-","Čeká na aktuální údaje ze sondy"
    print(f'{status} "Polarita {name}" {metrics} {summary}')
