#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T restic-test --)
"${inside[@]}" install -d /usr/local/lib/polarita-restic
incus file push --mode=0644 "$src/hovory_retence.py" restic-test/usr/local/lib/polarita-restic/
incus file push --mode=0644 "$src"/polarita-hovory-expirace.{timer,service} restic-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-hovory-expirace.timer
"${inside[@]}" systemctl start polarita-hovory-expirace.service
"${inside[@]}" systemctl is-active --quiet polarita-hovory-expirace.timer
