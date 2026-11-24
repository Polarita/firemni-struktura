#!/bin/bash
# Vlastní transakční fronta pro případy TEST, oddělená od tabulek výrobce Paperclip.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
sql=(incus exec -T postgres-test -- runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -d db_paperclip)
"${sql[@]}" <"$src/fronta.sql" >/dev/null
"${sql[@]}" <"$src/zkouska.sql" >/dev/null
echo 'Decisions TEST ověřil původní a navržený stav, obě akce, opakování požadavků, zákaz přímých změn a souhlasů navrhovatele, starou verzi a obě denní okna včetně změn času.'
python3 "$src/soubeh.py"
