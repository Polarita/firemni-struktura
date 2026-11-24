#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
bash "$src/../incus/balicky.sh" checkmk-test python3-aiosmtpd=1.4.6-6
inside=(incus exec -T checkmk-test --)
"${inside[@]}" install -d /usr/local/lib/polarita-dohled
incus file push --mode=0644 "$src/prijem_test.py" checkmk-test/usr/local/lib/polarita-dohled/
incus file push --mode=0644 "$src/polarita-alert-test.service" checkmk-test/etc/systemd/system/
site=/omd/sites/polarita
"${inside[@]}" install -d -m 0755 -o polarita -g polarita "$site/local/share/check_mk/notifications"
for plugin in polarita_smtp polarita_telegram; do
    incus file push --mode=0755 "$src/notifikace.py" "checkmk-test$site/local/share/check_mk/notifications/$plugin"
done
incus file push --mode=0644 "$src/polarita-notifikace.mk" "checkmk-test$site/etc/check_mk/conf.d/"
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-alert-test.service
"${inside[@]}" systemctl is-active --quiet polarita-alert-test.service
