#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T postgres-test --)
"${inside[@]}" runuser -u postgres -- psql -Xqw -v ON_ERROR_STOP=1 -d db_eshop <"$src/bubny.sql" >/dev/null
"${inside[@]}" python3 - <"$src/bubny-test.py"
