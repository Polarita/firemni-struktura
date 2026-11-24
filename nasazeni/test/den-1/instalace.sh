#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
[[ $(findmnt -no SOURCE --mountpoint /srv/polarita/vault) == polarita_zfs/vault ]]
src=$(cd "$(dirname "$0")" && pwd)
stage=$(mktemp -d)
trap 'rm -r -- "$stage"' EXIT
install -m0644 "$src/baze.py" "$stage/baze.py"
chmod 0755 "$stage"
runuser -u polarita-pamet -- python3 -Es "$stage/baze.py"
incus exec -T postgres-test -- runuser -u postgres -- psql -Xqw -d db_erp_lhutnik <"$src/terminy.sql"
for entry in 04-Pravo-a-Smlouvy/den-1-pravni-minimum.md 03-Normy-a-Metodiky/den-1-metodika.md 04-Pravo-a-Smlouvy/den-1-registr-zdroje.md; do
    sudo -u pol-vault-11001 /usr/local/bin/agent_vault get-context "$entry" |
        python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["cesta"]==sys.argv[1] and "evidence servisní poptávky" in r["text"] and "Datum znění" in r["text"]' "$entry"
done
echo 'Účet CEO ve stavu SHADOW přečetl právní minimum, metodiku i bibliografický záznam.'
