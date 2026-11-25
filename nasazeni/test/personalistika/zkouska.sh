#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
vysledky=$(unshare --net python3 -B "$src/pracovnici.py")
incus exec -T postgres-test -- runuser -u postgres -- psql -XqAtw -v ON_ERROR_STOP=1 \
    -d db_hr_lide -v "vysledky=$vysledky" <"$src/prehled.sql"
echo 'Čtecí role ověřila person_no a způsobilost každého vzoru. Soukromé důvody jsou přístupné jen v personální vrstvě TEST.'
