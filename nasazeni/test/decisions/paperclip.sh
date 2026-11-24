#!/bin/bash
set -euo pipefail
umask 077
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
fqdn=${1:?Chybí jméno firemní VPN}
sql=(incus exec -T postgres-test -- runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -d db_paperclip)
pc=(incus exec -T paperclip-test --)
manifest=$(mktemp)
trap 'rm -f -- "$manifest"' EXIT
exec 8>/run/polarita-test-decisions-instalace.lock
flock 8
"${sql[@]}" <"$src/paperclip.sql" >/dev/null
incus file push --mode=0644 "$src/priklady.py" paperclip-test/etc/polarita-paperclip/
pc_call() {
    "${pc[@]}" python3 /etc/polarita-paperclip/priklady.py "$fqdn" "$1" </srv/polarita/data/bootstrap-test/test-login/heslo
}
pc_call priprav >"$manifest"
"${sql[@]}" -v "vzor=$(cat "$manifest")" <"$src/prirad.sql"
incus exec -T postgres-test -- bash -se <"$src/most.sh"
pc_call vyzkousej
incus exec -T postgres-test -- systemctl start polarita-decisions.service
proof=$("${sql[@]}" -c "SELECT z.cislo,s.verze,s.stav,v.vysledek FROM polarita.test_vazba v JOIN polarita.test_rozhodnuti z ON z.id=v.navrh JOIN polarita.test_spis s USING(cislo) WHERE z.cislo IN ('TEST-POL-0000-00011','TEST-POL-0000-00012') ORDER BY z.cislo")
[[ $proof == $'TEST-POL-0000-00011|2|ke kontrole|potvrzeno\nTEST-POL-0000-00012|1|rozpracován|zamitnuto' ]]
store=/srv/polarita/data/paperclip
install -m 0600 "$manifest" "$store/.rozhodnuti.next"
mv -T "$store/.rozhodnuti.next" "$store/rozhodnuti.json"
echo 'Paperclip zapsal obě nativní volby správce TEST. Oddělená databázová služba ověřila jeho identitu a celý diff. Potvrzení změnilo první spis a zamítnutí zachovalo druhý.'
url=$(python3 - "$manifest" "$fqdn" <<'PY'
from pathlib import Path
import json
import sys
from uuid import UUID
item,=(r for r in json.loads(Path(sys.argv[1]).read_text()) if r['obsah']['polarita']['spis']=='TEST-POL-0000-00013')
print(f"https://{sys.argv[2]}:8445/approvals/{UUID(item['approval'])}")
PY
)
printf '%s\n' "$url" | incus exec -T reditelstvi-test -- sh -ec '
    umask 022
    dest=/usr/local/share/polarita-decisions-url
    cat > "$dest.next"
    mv -T "$dest.next" "$dest"
'
echo "Uživatelský vzor TEST-POL-0000-00013: $url"
