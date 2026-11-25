#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
fqdn=${1:?Chybí VPN jméno}
[[ $fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
inside=(incus exec -T paperclip-test --)
work=/srv/polarita/infra/paperclip-test
exec 9>"$work/.server"
flock 9
"${inside[@]}" test -s /opt/paperclip/current/node_modules/@paperclipai/server/ui-dist/index.html
"${inside[@]}" bash -se <<'INNER'
set -euo pipefail
getent group paperclip-test >/dev/null || groupadd --gid 17308 paperclip-test
id paperclip-test >/dev/null 2>&1 || useradd --uid 17308 --gid 17308 --home-dir /var/lib/paperclip --no-create-home --shell /usr/sbin/nologin paperclip-test
[[ $(id -u paperclip-test) == 17308 && $(id -g paperclip-test) == 17308 ]]
mountpoint -q /var/lib/paperclip
chown paperclip-test:paperclip-test /var/lib/paperclip
chmod 0700 /var/lib/paperclip
install -d -m 0755 /etc/polarita-paperclip
if ! getent ahostsv4 postgres.polarita.test >/dev/null; then
    echo '10.239.33.12 postgres.polarita.test' >> /etc/hosts
fi
[[ $(getent ahostsv4 postgres.polarita.test | awk '{print $1}' | sort -u) == 10.239.33.12 ]]
INNER
incus file push --mode=0644 "$src/start.sh" paperclip-test/etc/polarita-paperclip/
incus file push --mode=0644 "$src"/polarita-paperclip.{service,timer} paperclip-test/etc/systemd/system/
incus file push --mode=0644 /srv/polarita/infra/postgres-test/ca.crt paperclip-test/etc/polarita-paperclip/postgres.crt
# Drizzle má samostatný žurnál migrací. Vlastnictví omezujeme na schéma v databázi Paperclipu.
incus exec -T postgres-test -- runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -d db_paperclip <<'SQL'
GRANT CREATE ON DATABASE db_paperclip TO db_paperclip;
CREATE SCHEMA IF NOT EXISTS drizzle AUTHORIZATION db_paperclip;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
{
    printf 'PAPERCLIP_PUBLIC_URL=https://%s:8445\n' "$fqdn"
    printf 'PAPERCLIP_ALLOWED_HOSTNAMES=%s,localhost,127.0.0.1\n' "$fqdn"
    printf 'BETTER_AUTH_TRUSTED_ORIGINS=https://%s:8445\n' "$fqdn"
    if "${inside[@]}" test -f /etc/polarita-paperclip/spravce-overen; then
        echo PAPERCLIP_AUTH_DISABLE_SIGN_UP=true
    else
        echo PAPERCLIP_AUTH_DISABLE_SIGN_UP=false
    fi
} | "${inside[@]}" sh -ec 'umask 022; cat > /etc/polarita-paperclip/server.env.next; mv -T /etc/polarita-paperclip/server.env.next /etc/polarita-paperclip/server.env'
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-paperclip.timer
"${inside[@]}" systemctl reset-failed polarita-paperclip.service
"${inside[@]}" bash -se -- "$fqdn" <<'READY'
set -euo pipefail
marker=/etc/polarita-paperclip/spustena-konfigurace
signature=$({
    readlink -f /opt/paperclip/current
    /opt/node/bin/node --version
    sha256sum /etc/polarita-paperclip/{start.sh,postgres.crt,server.env} /etc/systemd/system/polarita-paperclip.service \
        /run/secrets/{pg-db_paperclip,paperclip-auth,paperclip-jwt,paperclip-master}
} | sha256sum | cut -d' ' -f1)
if [[ ! -f $marker || $(<"$marker") != "$signature" ]]; then
    systemctl restart polarita-paperclip.service
else
    systemctl start polarita-paperclip.service
fi
for step in {1..180}; do
    if curl -fsS -m 4 -H "Host: $1:8445" http://127.0.0.1:3100/api/health 2>/dev/null |
        python3 -c 'import json,sys;d=json.load(sys.stdin);sys.exit(d.get("status")!="ok" or d.get("deploymentMode")!="authenticated")' 2>/dev/null; then
        umask 077
        printf '%s\n' "$signature" >"$marker.next"
        mv -T "$marker.next" "$marker"
        echo 'Paperclip dokončil migrace a jeho nativní API odpovědělo v režimu s ověřením identity.'
        exit 0
    fi
    if systemctl is-failed --quiet polarita-paperclip.service; then exit 1; fi
    sleep 3
done
exit 1
READY
