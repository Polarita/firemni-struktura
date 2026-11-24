"""Odesílá čas skutečného vyhodnocení služby z jádra Checkmk na lokální záložní uzel."""
import json
import socket
import subprocess
import time

if socket.gethostname().split(".")[0]!="polarita-hq":
    raise SystemExit("Signál je určen pro firemní VM")
now=int(time.time())
result=subprocess.run(["incus","exec","-T","checkmk-test","--","runuser","-u","polarita","--",
                       "python3","/usr/local/lib/polarita-dohled/livestatus.py"],capture_output=True,timeout=15)
cmk=0
if result.returncode==0:
    live=json.loads(result.stdout)
    cmk=live.get("Polarita aktualnost sond",{}).get("cas",0)
subprocess.run(["incus","exec","-T","restic-test","--","runuser","-u","pol-watchdog","--",
                "python3","/usr/local/lib/polarita-watchdog/watchdog.py","--prijem"],
               input=json.dumps({"polarita-hq":now,"checkmk":cmk}).encode(),check=True,timeout=15)

# Portál může číst pouze tento přehled. Administrátorské rozhraní zůstává na loopbacku.
if cmk:
    subprocess.run(["incus","exec","-T","reditelstvi-test","--","sh","-ec",
                    'cd /usr/local/share; t=$(mktemp .dohled-XXXXXXXX); cat >"$t"; chmod 0644 "$t"; mv -f "$t" polarita-dohled.json'],
                   input=json.dumps(live).encode(),check=True,timeout=10)
