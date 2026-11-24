#!/bin/bash
# Druhý PostgreSQL uvnitř dočasné instance ověří skutečné zastavení před pozdějším WAL záznamem.
set -euo pipefail
[[ $(hostname -s) =~ ^restic-obnova-[a-f0-9]{12}$ && $(ls /sys/class/net) == lo && $EUID == 0 ]]
source_dir=/var/tmp/obnova-polarita
read -r target before after <"$source_dir/pitr-cil.txt"
[[ $target =~ ^polarita_[a-f0-9]{32}$ && $before =~ ^[0-9A-F]+/[0-9A-F]+$ && $after =~ ^[0-9A-F]+/[0-9A-F]+$ ]]
work=/var/lib/postgresql/obnova-pitr
pg=(runuser -u postgres --)
install -d -m 0700 -o postgres -g postgres "$work" "$work/db" "$work/repo" "$work/socket"
"${pg[@]}" tar --no-same-owner -xf - -C "$work/repo" <"$source_dir/pgbackrest.tar"
cat >"$work/pgbackrest.conf" <<CONF
[global]
repo1-path=$work/repo
process-max=1
log-level-console=warn
log-level-file=off
[polarita]
pg1-path=$work/db
CONF
chmod 0644 "$work/pgbackrest.conf"
"${pg[@]}" pgbackrest --config="$work/pgbackrest.conf" --stanza=polarita --type=name --target="$target" --target-action=pause restore
cat >"$work/postgresql.conf" <<CONF
listen_addresses = ''
port = 55432
unix_socket_directories = '$work/socket'
hba_file = '$work/pg_hba.conf'
ident_file = '$work/pg_ident.conf'
ssl = off
shared_buffers = '16MB'
max_connections = 48
archive_mode = off
hot_standby = on
CONF
echo 'local all postgres peer' >"$work/pg_hba.conf"
touch "$work/pg_ident.conf"
chmod 0644 "$work"/{postgresql,pg_hba,pg_ident}.conf
ctl=("${pg[@]}" /usr/lib/postgresql/18/bin/pg_ctl -D "$work/db")
"${ctl[@]}" -w start -t 90 -l "$work/restore.log" -o "-c config_file=$work/postgresql.conf" || { tail -n 12 "$work/restore.log" >&2; exit 1; }
trap '"${ctl[@]}" -m fast -w stop >/dev/null' EXIT
sql=("${pg[@]}" psql -XqAt -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432)
for i in {1..60}; do
    if [[ $("${sql[@]}" -d postgres -c 'SELECT pg_get_wal_replay_pause_state()') == paused ]]; then break; fi
    sleep 1
done
[[ $("${sql[@]}" -d postgres -c "SELECT pg_is_in_recovery() AND pg_get_wal_replay_pause_state()='paused' AND pg_last_wal_replay_lsn()>='$before'::pg_lsn AND pg_last_wal_replay_lsn()<'$after'::pg_lsn") == t ]]
[[ $("${sql[@]}" -d keycloak -c "SELECT count(*) FROM user_entity WHERE username='spravce'") == 1 ]]
echo 'pgBackRest obnovil z Restic kopie databázi Keycloak v zadaném bodě WAL. Pozdější WAL záznam se do obnovené databáze nepromítl.'
