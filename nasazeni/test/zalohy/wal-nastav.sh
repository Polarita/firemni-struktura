#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == postgres-test && $EUID == 0 ]]
exec 8>/run/polarita-wal.lock
flock -w 1800 8
data=/var/lib/polarita-postgres
mountpoint -q "$data"
install -d -m 0755 /etc/pgbackrest
install -d -m 0700 -o postgres -g postgres "$data/pgbackrest"
cat >/etc/pgbackrest/polarita.conf <<'CONF'
[global]
repo1-path=/var/lib/polarita-postgres/pgbackrest
repo1-retention-full=2
repo1-bundle=y
compress-type=zst
process-max=1
start-fast=y
log-level-console=warn
log-level-file=off
[polarita]
pg1-path=/var/lib/polarita-postgres/db
pg1-socket-path=/run/postgresql
CONF
cat >/etc/polarita-postgres/archivace.conf <<'CONF'
archive_mode = on
archive_command = '/usr/bin/pgbackrest --config=/etc/pgbackrest/polarita.conf --stanza=polarita archive-push %p'
archive_timeout = '15min'
CONF
chmod 0644 /etc/pgbackrest/polarita.conf /etc/polarita-postgres/archivace.conf
include="include_if_exists = '/etc/polarita-postgres/archivace.conf'"
grep -qFx "$include" /etc/polarita-postgres/postgresql.conf || echo "$include" >>/etc/polarita-postgres/postgresql.conf
pg=(runuser -u postgres --)
sql=("${pg[@]}" psql -XqAt -v ON_ERROR_STOP=1 -d postgres)
if [[ $("${sql[@]}" -c 'show archive_mode') != on ]]; then
    systemctl restart polarita-postgres.service
else
    systemctl reload polarita-postgres.service
fi
[[ $("${sql[@]}" -c 'show archive_mode') == on ]]
backrest=("${pg[@]}" pgbackrest --config=/etc/pgbackrest/polarita.conf --stanza=polarita)
"${backrest[@]}" stanza-create
"${backrest[@]}" check
echo 'PostgreSQL potvrdil archivaci WAL. Vynucené uzavření neplného segmentu je nastavené po 15 minutách.'
