#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == postgres-test && $EUID == 0 ]]
pg=(runuser -u postgres --)
sql=("${pg[@]}" psql -XqAt -v ON_ERROR_STOP=1 -d postgres)
backrest=("${pg[@]}" pgbackrest --config=/etc/pgbackrest/polarita.conf --stanza=polarita)
# V neděli uchovej novou úplnou zálohu, ostatní dny stačí rozdílová.
kind=diff
if [[ $(date -u +%u) == 7 ]] || ! "${backrest[@]}" info --output=json | python3 -c 'import json,sys; sys.exit(not json.load(sys.stdin)[0]["backup"])'; then
    kind=full
fi
"${backrest[@]}" --type="$kind" backup
target="polarita_$(tr -d - </proc/sys/kernel/random/uuid)"
[[ $target =~ ^polarita_[a-f0-9]{32}$ ]]
# Dva pojmenované body jsou součástí WAL. Nepotřebují zápis do firemních tabulek.
before=$("${sql[@]}" -c "SELECT pg_create_restore_point('$target')")
after=$("${sql[@]}" -c "SELECT pg_create_restore_point('${target}_po')")
wal=$("${sql[@]}" -c "SELECT pg_walfile_name('$after')")
"${sql[@]}" -c 'SELECT pg_switch_wal()' >/dev/null
[[ $wal =~ ^[0-9A-F]{24}$ ]]
dir=$("${pg[@]}" mktemp -d /var/tmp/polarita-wal-XXXXXXXX)
trap 'rm -rf -- "$dir"' EXIT
for i in {1..45}; do
    if "${backrest[@]}" archive-get "$wal" "$dir/segment" >/dev/null 2>&1; then break; fi
    sleep 1
done
[[ -s $dir/segment && $before =~ ^[0-9A-F]+/[0-9A-F]+$ && $after =~ ^[0-9A-F]+/[0-9A-F]+$ ]]
echo "$target $before $after"
