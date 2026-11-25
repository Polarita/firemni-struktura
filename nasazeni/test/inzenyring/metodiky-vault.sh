#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
[[ $(findmnt -no SOURCE --mountpoint /srv/polarita/vault) == polarita_zfs/vault ]]
src=$(cd "$(dirname "$0")" && pwd)
api=$src/../metadata-schema-kernel
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
chmod 0755 "$tmp"
install -m0644 "$src/metodiky_vault.py" "$api"/{model,metodiky,registr_metodik}.py "$api"/*-metodiky-test.json "$tmp/"
runuser -u polarita-pamet -- python3 -Es "$tmp/metodiky_vault.py" --zapis >"$tmp/registr.json"
# Normovač musí přečíst stejné stránky prostřednictvím běžného rozhraní své role.
python3 - "$tmp/registr.json" <<'PYTHON'
import json,subprocess,sys
for path, stranka in json.load(open(sys.argv[1]))["stranky"].items():
    raw = subprocess.check_output(["runuser","-u","pol-vault-15002","--","/usr/local/bin/agent_vault","get-context",path])
    data = json.loads(raw)
    if data["cesta"] != path or data["text"] != stranka["text"]:
        raise ValueError("Čtecí rozhraní normovače nepotvrdilo znění stránky.")
PYTHON
run=(incus exec -T postgres-test --)
dest=$("${run[@]}" mktemp -d)
trap '"${run[@]}" rm -rf -- "$dest"; rm -rf -- "$tmp"' EXIT
(cd "$tmp" && tar -cf - -- *.py *-metodiky-test.json) | "${run[@]}" tar -xf - -C "$dest"
"${run[@]}" python3 -Es "$dest/metodiky_vault.py" --prijmi <"$tmp/registr.json"
