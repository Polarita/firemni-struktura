#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T medusa-test --)
root=/srv/polarita/apps/medusa-test
rev=$(readlink "$root/current")
[[ $rev =~ ^releases/[a-f0-9]{64}$ ]]
incus file push --mode=0644 "$src/over_db.cjs" medusa-test/etc/polarita-medusa/over_db.cjs
incus exec -T medusa-test --user 17309 --group 17309 -- /opt/node/bin/node /etc/polarita-medusa/over_db.cjs
incus file push --mode=0644 "$src/polarita-medusa.service" medusa-test/etc/systemd/system/polarita-medusa.service
"${inside[@]}" bash -se -- "$rev" <<'RUN'
set -euo pipefail
exec 9>/run/polarita-medusa-migrace.lock
flock 9
install -dm0750 -o medusa -g medusa /var/lib/medusa
systemctl daemon-reload
active=$(cat /var/lib/medusa/.spustena-revize 2>/dev/null || true)
if [[ $active != "$1" ]]; then
    systemd-run --quiet --pipe --wait --collect --service-type=exec -p User=medusa -p Group=medusa \
        -p 'WorkingDirectory=/opt/medusa/current/.medusa/server' -p NoNewPrivileges=yes -p PrivateTmp=yes \
        -E PATH=/opt/node/bin:/usr/bin:/bin -E NODE_ENV=production -E MEDUSA_DISABLE_TELEMETRY=true \
        -E HOME=/var/lib/medusa -E NODE_OPTIONS=--max-old-space-size=550 \
        /opt/node/bin/node /opt/medusa/current/node_modules/@medusajs/cli/cli.js db:migrate \
            --concurrency 1 --execute-safe-links --execute-safe-search
    systemctl restart polarita-medusa
fi
systemctl enable --now polarita-medusa
for i in {1..100}; do
    if curl -fsS --max-time 5 http://127.0.0.1:9000/health 2>/dev/null | grep -Fq OK; then
        [[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:9000/admin/reklamace) == 401 ]]
        [[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:9000/app/) == 200 ]]
        printf '%s\n' "$1" >/var/lib/medusa/.spustena-revize
        echo 'Medusa poskytla odpověď /health a správní web. Anonymní přístup k reklamacím byl odmítnut.'
        exit 0
    fi
    sleep 4
done
exit 1
RUN
