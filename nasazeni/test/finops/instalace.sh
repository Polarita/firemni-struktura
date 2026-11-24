#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
sql=(incus exec -T postgres-test -- runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -d db_paperclip)
"${sql[@]}" <"$src/rozpocet.sql" >/dev/null
incus exec -T postgres-test -- python3 - <"$src/pristup.py"
incus exec -T postgres-test -- runuser -u pol_finops_read -- psql -wXqAt -v ON_ERROR_STOP=1 -d db_paperclip \
    -c "SELECT jsonb_array_length(polarita_finops.stav()->'pozice')" | grep -qx 20
python3 "$src/zkouska.py"
python3 "$src/nativni.py" "${1:?Chybí adresa firemní VPN}"
