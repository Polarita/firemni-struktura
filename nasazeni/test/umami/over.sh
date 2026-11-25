#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
exec 9>/run/polarita-umami-overeni.lock
flock 9
inside=(incus exec -T umami-test --user 1001 --group 1001 --)
for i in {1..90}; do
    if "${inside[@]}" curl -fsS --max-time 3 --output /dev/null http://127.0.0.1:3000/api/heartbeat 2>/dev/null; then break; fi
    sleep 4
done
"${inside[@]}" node /etc/polarita-umami/over.mjs </srv/polarita/data/bootstrap-test/test-login/heslo
src=$(cd "$(dirname "$0")" && pwd)
install -m0644 "$src/sber.py" /srv/polarita/infra/umami-test/sber.py
install -m0644 "$src"/polarita-umami-sber.{service,timer} /etc/systemd/system/
# Sběr a přejímka nesmějí současně odesílat stejnou událost.
flock -u 9
systemctl daemon-reload
systemctl start polarita-umami-sber.service
systemctl enable --now polarita-umami-sber.timer
flock 9
/opt/polarita-ads-mcp-test/current/sdk/bin/python -I "$src/over_mcp.py"
