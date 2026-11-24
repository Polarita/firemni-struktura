#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/checkmk-test
data=/srv/polarita/data/checkmk
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
bash "$src/distribuce.sh"
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/data) == polarita_zfs/data ]]
if ! zfs list -Ho name polarita_zfs/data/checkmk >/dev/null 2>&1; then
    [[ ! -e $data ]]
    zfs create -o mountpoint="$data" -o devices=off -o setuid=off polarita_zfs/data/checkmk
fi
[[ $(findmnt -n -o SOURCE --mountpoint "$data") == polarita_zfs/data/checkmk ]]
[[ $(zfs get -Ho value encryptionroot polarita_zfs/data/checkmk) == polarita_zfs ]]
install -d -m 0755 "$data/test"
cd "$work/tofu"
install -m 0644 "$src/checkmk.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
tofu init -input=false -lockfile=readonly
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    a=r["change"]["actions"]
    if a in (["no-op"],["read"]) or (r["address"]=="incus_instance.dohled" and a in (["create"],["update"])): continue
    sys.exit("Neočekávaná změna "+r["address"])'
tofu apply -input=false "$tmp/plan"
incus exec -T checkmk-test -- bash -ec 'for i in {1..60}; do if test -S /run/systemd/private && mountpoint -q /opt/omd/sites; then exit 0; fi; sleep 1; done; exit 1'
bash "$src/balicky.sh"
incus exec -T checkmk-test -- bash -se <"$src/lokalita.sh"
tofu plan -input=false -detailed-exitcode
