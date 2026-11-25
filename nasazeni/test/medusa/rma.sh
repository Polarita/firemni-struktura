#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
db=(incus exec -T postgres-test -- runuser -u postgres -- psql -Xqw -v ON_ERROR_STOP=1 -d db_eshop)
"${db[@]}" <"$src/rma.sql" >/dev/null
"${db[@]}" <"$src/rma-test.sql"
printf 'Elektro WMS · role db_eshop ověřila dvě reklamace, odlišné časy přijetí a uplatnění, opakování požadavků a odmítnutí přepisu. Zkušební transakce byla vrácena.\n'
