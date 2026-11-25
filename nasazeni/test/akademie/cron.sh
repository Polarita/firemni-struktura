#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T akademie-test --)
"${inside[@]}" test -s /etc/polarita-akademie/schema
"${inside[@]}" test -f /opt/polarita-akademie/current/admin/cli/cron.php
for ext in service timer; do
    unit=polarita-moodle-cron.$ext
    incus file push --mode=0644 "$src/$unit" "akademie-test/etc/systemd/system/.$unit.next"
    "${inside[@]}" mv -T "/etc/systemd/system/.$unit.next" "/etc/systemd/system/$unit"
done
"${inside[@]}" systemd-analyze verify polarita-moodle-cron.service polarita-moodle-cron.timer
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-moodle-cron.timer
"${inside[@]}" systemctl is-active --quiet polarita-moodle-cron.timer
