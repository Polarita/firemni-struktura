#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
[[ $src =~ ^/srv/polarita/infra/(stavba|releases)/[0-9a-f]{40}/nasazeni/test/zalohy$ ]]
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
for phase in sber obnova hovory; do
    cmd=sber.py
    if [[ $phase == obnova ]]; then cmd=obnov.py; fi
    if [[ $phase == hovory ]]; then cmd=hovory_sber.py; fi
    unit=polarita-restic-$phase
    cat >"$tmp/$unit.service" <<UNIT
[Unit]
Description=Restic TEST – $phase uvnitř polarita-hq
After=incus.service
RequiresMountsFor=/srv/polarita/backups/restic-test /srv/polarita/infra/restic-test
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $src/$cmd
TimeoutStartSec=50min
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
UMask=0077
UNIT
    install -m 0644 "$tmp/$unit.service" "$src/$unit.timer" /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable --now polarita-restic-sber.timer polarita-restic-obnova.timer polarita-restic-hovory.timer
systemctl is-active --quiet polarita-restic-sber.timer
systemctl is-active --quiet polarita-restic-obnova.timer
