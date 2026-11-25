#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
pg=(incus exec -T postgres-test -- runuser -u postgres -- psql -Xqw -v ON_ERROR_STOP=1 -d db_gdpr_zkousky)
"${pg[@]}" <"$src/prehled.sql" >/dev/null
"${pg[@]}" <"$src/prehled-test.sql" >/dev/null
echo 'V db_gdpr_zkousky přečetla role polarita_ai_masked ve třech pohledech pouze person_no a příznak způsobilosti. Přístup k původním údajům byl zamítnut.'
echo 'Cvičná data ověřila šifrování pgcrypto, tři různé členy zkušební komise, následný neúspěch, konec platnosti a skrytí nezaloženého archivního dokladu.'
