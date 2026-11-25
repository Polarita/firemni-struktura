#!/bin/bash
set -euo pipefail
umask 077
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
unshare --net sh -ec 'ip link set lo up; exec python3 -B "$1/zkouska_vypisu.py" --ledger "$2"' -- "$src" "$tmp/polozky.json"
db=(incus exec -T postgres-test -- runuser -u postgres -- psql -XqAtw -d db_erp_lhutnik -v VERBOSITY=verbose -v ON_ERROR_STOP=1)
zapis() {
    "${db[@]}" -v "polozky=$1" <"$src/provize.sql"
}
polozky=$(cat "$tmp/polozky.json")
zapis "$polozky" >"$tmp/prvni.txt"
zapis "$polozky" >"$tmp/opakovani.txt"
cmp "$tmp/prvni.txt" "$tmp/opakovani.txt"
[[ $(wc -l <"$tmp/prvni.txt") -eq 3 ]]
# Platný řádek s jiným partnerem je konflikt historie, také když před ním přišla nová událost.
kolize=$(python3 - "$tmp/polozky.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
print(json.dumps([rows[0] | {"udalost": "TEST-ROLLBACK-PROVIZE"}, rows[0] | {"partner": "SUB-TEST-ZMENA"}]))
PY
)
if zapis "$kolize" >"$tmp/kolize.txt" 2>&1; then
    echo 'Ledger přijal konfliktní podklad.' >&2
    exit 1
fi
grep -q 'PZ001:' "$tmp/kolize.txt"
[[ $(printf '%s\n' "SET ROLE pol_provize_zapis; SELECT count(*) FROM polarita_registr_test.provizni_ledger WHERE udalost='TEST-ROLLBACK-PROVIZE';" | "${db[@]}") == 0 ]]
cat "$tmp/prvni.txt"
echo 'Opakovaný import vrátil shodné položky. Konfliktní dávka se celá vrátila zpět.'
