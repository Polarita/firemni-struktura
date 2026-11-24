#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
[[ $src =~ ^/srv/polarita/infra/(stavba|releases)/[0-9a-f]{40}/nasazeni/test/dohled$ ]]
install -m 0644 "$src"/polarita-dohled-{sber.timer,vzorek.socket,vzorek@.service} /etc/systemd/system/
cat >/etc/systemd/system/polarita-dohled-sber.service <<UNIT
[Unit]
Description=Čtecí sondy dostupnosti testovacího ředitelství
After=incus.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $src/sbirej.py
ExecStartPost=/usr/bin/python3 $src/signal.py
TimeoutStartSec=60s
UMask=0077
UNIT
systemctl daemon-reload
systemctl enable --now polarita-dohled-vzorek.socket polarita-dohled-sber.timer
systemctl start polarita-dohled-sber.service
incus exec -T checkmk-test -- install -d -m 0755 /usr/local/lib/polarita-dohled
incus file push --mode=0644 "$src/agent.py" checkmk-test/usr/local/lib/polarita-dohled/
incus exec -T checkmk-test -- runuser -u nobody -- python3 /usr/local/lib/polarita-dohled/agent.py
