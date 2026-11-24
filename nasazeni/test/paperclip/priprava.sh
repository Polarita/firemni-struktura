#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/paperclip-test
store=/srv/polarita/data/paperclip
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/data) == polarita_zfs/data ]]
if ! zfs list -Ho name polarita_zfs/data/paperclip >/dev/null 2>&1; then
    [[ ! -e $store ]]
    zfs create -o mountpoint="$store" -o setuid=off -o devices=off polarita_zfs/data/paperclip
fi
[[ $(findmnt -n -o SOURCE --mountpoint "$store") == polarita_zfs/data/paperclip ]]
[[ $(zfs get -Ho value encryptionroot polarita_zfs/data/paperclip) == polarita_zfs ]]
install -d "$store/test"
bash "$src/distribuce.sh"
cd "$work/tofu"
install -m 0644 "$src/paperclip.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
python3 "$src/pozice.py" >"$tmp/pozice.json"
install -m 0600 "$tmp/pozice.json" "$store/pozice.json.next"
mv -T "$store/pozice.json.next" "$store/pozice.json"
tofu init -input=false -lockfile=readonly
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json, sys
for change in json.load(sys.stdin).get("resource_changes", []):
    actions = change["change"]["actions"]
    if actions in (["no-op"], ["read"]): continue
    if change["address"] == "incus_instance.paperclip" and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + change["address"])'
tofu apply -input=false "$tmp/plan"
inside=(incus exec -T paperclip-test --)
"${inside[@]}" bash -ec 'for i in {1..60}; do if test -S /run/systemd/private && mountpoint -q /var/lib/paperclip; then exit 0; fi; sleep 1; done; exit 1'
"${inside[@]}" /opt/node/bin/node -e 'if (process.version !== "v24.22.3") process.exit(1); console.log("Paperclip má připravený Node.js", process.version)'
tofu plan -input=false -detailed-exitcode
