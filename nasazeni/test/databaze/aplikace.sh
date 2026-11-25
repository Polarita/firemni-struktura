#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/srv/polarita/infra/postgres-test/.ucty
flock 8
mapfile -t dbs < <(PYTHONPATH="$src/../trezor" python3 -c 'import pristupy; print(*pristupy.DATABASES, sep="\n")')
[[ ${#dbs[@]} == 15 ]]
incus exec -T postgres-test -- python3 - "${dbs[@]}" <"$src/vytvoreni.py"
incus exec -T postgres-test -- runuser -u postgres -- psql -Xqw -d db_erp_lhutnik <"$src/../registry/rady.sql"
mapfile -t routes < <(python3 -c '
import json, sys
routes=json.load(open(sys.argv[1]))
assert set(routes) == set(sys.argv[2:])
for name, route in routes.items():
    assert route["pool_mode"] in ("session", "transaction")
    print(name + "=" + route["pool_mode"])' "$src/pripojeni.lock.json" "${dbs[@]}")
[[ ${#routes[@]} == 15 ]]
incus exec -T postgres-test -- bash -s -- "${routes[@]}" <"$src/pool.sh"
incus exec -T postgres-test -- python3 - "${dbs[@]}" <"$src/zkouska.py"
