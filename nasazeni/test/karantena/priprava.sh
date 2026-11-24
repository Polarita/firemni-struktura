#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/karantena-test
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
for dataset in airgap-spool clamav-db; do
    [[ $(findmnt -n -o SOURCE --mountpoint "/srv/polarita/data/$dataset") == "polarita_zfs/data/$dataset" ]]
    [[ $(zfs get -H -o value keystatus "polarita_zfs/data/$dataset") == available ]]
done
install -d -m 0755 /srv/polarita/data/airgap-spool/test/in /srv/polarita/data/clamav-db/test
install -d -m 0700 -o 17304 -g 17304 /srv/polarita/data/airgap-spool/test/out
image=$(sed -nE 's/^ *image *= *"local:([[:xdigit:]]{64})"$/\1/p' "$src/worker.tf")
[[ $image =~ ^[0-9a-f]{64}$ ]]
if ! incus image info "$image" >/dev/null 2>&1; then
    incus image copy "images:$image" local: --vm
fi
cd "$work/tofu"
install -m 0644 "$src/worker.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    a = r["change"]["actions"]
    if a in (["no-op"], ["read"]): continue
    if r["address"] == "incus_instance.karantena" and a in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
