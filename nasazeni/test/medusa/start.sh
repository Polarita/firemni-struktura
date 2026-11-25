#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T medusa-test --)
host=${1:-}
if [[ -z $host ]]; then
    url=$(incus exec -T gitea-test -- cat /etc/polarita-gitea/url)
    host=${url#https://}
    host=${host%%/*}
fi
[[ $host =~ ^[a-z0-9.-]+[.]ts[.]net$ ]]
printf 'MEDUSA_TEST_ORIGIN=https://%s:8450\n' "$host" | "${inside[@]}" sh -ec 'umask 022; cat > /etc/polarita-medusa/.vstup-next; mv -T /etc/polarita-medusa/.vstup-next /etc/polarita-medusa/vstup.env'
root=/srv/polarita/apps/medusa-test
exec 9>/run/polarita-medusa-spusteni.lock
flock 9
rev=$(readlink "$root/candidate")
[[ $rev =~ ^releases/[a-f0-9]{64}$ ]]
previous=$(readlink "$root/current" || true)
[[ -z $previous || $previous =~ ^releases/[a-f0-9]{64}$ ]]
incus file push --mode=0644 "$src/over_db.cjs" medusa-test/etc/polarita-medusa/over_db.cjs
incus exec -T medusa-test --user 17309 --group 17309 -- /opt/node/bin/node /etc/polarita-medusa/over_db.cjs "/opt/medusa/$rev/package.json"
incus file push --mode=0644 "$src/over_moduly.cjs" medusa-test/etc/polarita-medusa/over_moduly.cjs
incus exec -T medusa-test --user 17309 --group 17309 -- /opt/node/bin/node /etc/polarita-medusa/over_moduly.cjs "/opt/medusa/$rev"
incus file push --mode=0644 "$src/polarita-medusa.service" medusa-test/etc/systemd/system/polarita-medusa.service
"${inside[@]}" install -dm0750 -o medusa -g medusa /var/lib/medusa
"${inside[@]}" systemctl daemon-reload
active=$("${inside[@]}" sh -c 'cat /etc/polarita-medusa/spustena-revize 2>/dev/null || true')
# Po vypršení kontroly může první start dál načítat moduly již zmigrované verze.
running=$("${inside[@]}" sh -c 'p=$(systemctl show polarita-medusa -p MainPID --value); if [ "${p:-0}" != 0 ]; then readlink -e "/proc/$p/cwd" || true; fi')
resumed=false
if [[ $previous == "$rev" && $running == "/opt/medusa/$rev/.medusa/server" ]] && "${inside[@]}" test -f /etc/polarita-medusa/spravce-pripraven; then
    resumed=true
fi
if [[ $previous != "$rev" || ( $active != "$rev" && $resumed != true ) ]]; then
    "${inside[@]}" systemd-run --quiet --pipe --wait --collect --service-type=exec -p User=medusa -p Group=medusa \
        -p "WorkingDirectory=/opt/medusa/$rev/.medusa/server" -p NoNewPrivileges=yes -p PrivateTmp=yes \
        -E PATH=/opt/node/bin:/usr/bin:/bin -E NODE_ENV=production -E MEDUSA_DISABLE_TELEMETRY=true \
        -E HOME=/var/lib/medusa -E NODE_OPTIONS=--max-old-space-size=550 \
        /opt/node/bin/node "/opt/medusa/$rev/node_modules/@medusajs/cli/cli.js" db:migrate \
            --concurrency 1 --execute-safe-links --execute-safe-search
    if ! "${inside[@]}" test -f /etc/polarita-medusa/spravce-pripraven; then
        "${inside[@]}" systemd-run --quiet --pipe --wait --collect --service-type=exec -p User=medusa -p Group=medusa \
            -p "WorkingDirectory=/opt/medusa/$rev/.medusa/server" -p NoNewPrivileges=yes -p PrivateTmp=yes \
            -E PATH=/opt/node/bin:/usr/bin:/bin -E NODE_ENV=production -E MEDUSA_DISABLE_TELEMETRY=true \
            -E HOME=/var/lib/medusa -E NODE_OPTIONS=--max-old-space-size=550 \
            /opt/node/bin/node "/opt/medusa/$rev/node_modules/@medusajs/cli/cli.js" exec ./src/scripts/spravce.js \
            </srv/polarita/data/bootstrap-test/test-login/heslo
        "${inside[@]}" touch /etc/polarita-medusa/spravce-pripraven
    fi
    ln -sfn "$rev" "$root/.current-next"
    mv -Tf "$root/.current-next" "$root/current"
fi
activate() {
    "${inside[@]}" bash -se -- "$rev" "$resumed" <<'RUN'
set -euo pipefail
if [[ $2 != true ]]; then systemctl restart polarita-medusa; fi
systemctl enable --now polarita-medusa
deadline=$((SECONDS + 1800))
while (( SECONDS < deadline )); do
    if systemctl is-failed --quiet polarita-medusa; then exit 1; fi
    if curl -fsS --max-time 5 http://127.0.0.1:9000/health 2>/dev/null | grep -Fq OK; then
        [[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:9000/admin/reklamace/00000000-0000-4000-8000-000000000000) == 401 ]]
        curl -fsSL --max-redirs 2 --max-time 15 http://127.0.0.1:9000/app/ -o /dev/null
        printf '%s\n' "$1" >/etc/polarita-medusa/.revize-next
        mv -T /etc/polarita-medusa/.revize-next /etc/polarita-medusa/spustena-revize
        echo 'Medusa poskytla odpověď /health a správní web. Anonymní přístup k reklamacím byl odmítnut.'
        exit 0
    fi
    sleep 4
done
echo "Medusa zatím neposkytla /health a správní web." >&2
exit 75
RUN
}
incus file push --mode=0644 "$src/prihlaseni.py" medusa-test/etc/polarita-medusa/prihlaseni.py
if ! activate || ! "${inside[@]}" python3 /etc/polarita-medusa/prihlaseni.py 127.0.0.1 </srv/polarita/data/bootstrap-test/test-login/heslo; then
    if [[ -n $previous && $previous != "$rev" ]]; then
        ln -sfn "$previous" "$root/.current-next"
        mv -Tf "$root/.current-next" "$root/current"
        "${inside[@]}" systemctl restart polarita-medusa
    fi
    exit 1
fi
