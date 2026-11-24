#!/bin/bash
# Spouští se výhradně v postgres-test. Pouze strojový účet mostu smí převzít ověřené hlasy.
set -euo pipefail
[[ $(hostname -s) == postgres-test && $EUID == 0 ]]
if ! getent passwd pol_decisions_bridge >/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin pol_decisions_bridge
fi
conf=/etc/polarita-postgres/pg_hba.conf
python3 - "$conf" <<'PY'
from pathlib import Path
import os
import sys
import tempfile
p=Path(sys.argv[1])
lines=p.read_text().splitlines()
line='local db_paperclip pol_decisions_bridge peer'
if line not in lines:
    idx=lines.index('local all postgres peer')
    lines.insert(idx+1,line)
    with tempfile.NamedTemporaryFile('w',dir=p.parent,delete=False) as f:
        f.write('\n'.join(lines)+'\n')
        os.fchmod(f.fileno(),0o644)
    os.replace(f.name,p)
elif lines.index(line)>lines.index('local all all scram-sha-256'):
    raise RuntimeError('Před lokálním účtem mostu je jiné pravidlo')
PY
systemctl reload polarita-postgres.service
cat >/etc/systemd/system/polarita-decisions.service <<'UNIT'
[Unit]
Description=Převzetí ověřených hlasů Paperclipu pro vzorové spisy TEST
After=polarita-postgres.service
[Service]
Type=oneshot
User=pol_decisions_bridge
ExecStart=/usr/bin/psql -XqAtw -v ON_ERROR_STOP=1 -d db_paperclip -c "SELECT polarita.test_prevez()"
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
RestrictAddressFamilies=AF_UNIX
UNIT
cat >/etc/systemd/system/polarita-decisions.timer <<'UNIT'
[Unit]
Description=Kontrola vzorových rozhodnutí ve firemní databázi
[Timer]
OnBootSec=45s
OnUnitInactiveSec=20s
AccuracySec=2s
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now polarita-decisions.timer
systemctl start polarita-decisions.service
