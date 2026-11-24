#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T restic-test --)
"${inside[@]}" sh -ec 'getent passwd pol-watchdog >/dev/null || useradd --system --user-group --home-dir /nonexistent --shell /usr/sbin/nologin pol-watchdog; install -d /usr/local/lib/polarita-watchdog; install -d -m 0700 -o pol-watchdog -g pol-watchdog /var/lib/polarita-watchdog'
incus file push --mode=0644 "$src/watchdog.py" restic-test/usr/local/lib/polarita-watchdog/
incus file push --mode=0644 "$src"/polarita-watchdog.{service,timer} restic-test/etc/systemd/system/
incus exec -T checkmk-test -- install -d /usr/local/lib/polarita-dohled
incus file push --mode=0644 "$src/livestatus.py" checkmk-test/usr/local/lib/polarita-dohled/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-watchdog.timer
"${inside[@]}" runuser -u pol-watchdog -- python3 /usr/local/lib/polarita-watchdog/watchdog.py --zkouska
