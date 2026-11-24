#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
bash "$src/../incus/balicky.sh" restic-test restic=0.18.1-3ubuntu1
inside=(incus exec -T restic-test --)
"${inside[@]}" install -d -m 0700 -o root -g root /etc/polarita-restic/sprava
# Dešifrovací údaj je předán po Incus jen do místního strojového účtu údržby.
python3 - "$src" <<'PY'
import sys,subprocess
sys.path.insert(0,sys.argv[1])
from pristup import credential
subprocess.run(["incus","exec","-T","restic-test","--","sh","-ec","umask 077; cd /etc/polarita-restic/sprava; cat >.heslo-next; chmod 0400 .heslo-next; mv -T .heslo-next heslo"],
               input=credential("restic-repozitar").encode(),check=True)
PY
incus file push --mode=0644 "$src"/polarita-restic-retence.{timer,service} restic-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-restic-retence.timer
"${inside[@]}" systemctl start polarita-restic-retence.service
"${inside[@]}" systemctl is-active --quiet polarita-restic-retence.timer
"${inside[@]}" systemctl show -p Result polarita-restic-retence.service | grep -Fx Result=success
