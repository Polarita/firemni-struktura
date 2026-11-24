#!/bin/sh
# Spouští se jako root uvnitř firemní VM po inicializaci jejího Incusu.
set -eu
test "$(hostname -s)" = polarita-hq
test "$(systemd-detect-virt)" = kvm
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd /srv/polarita/infra/incus
test -f .terraform.lock.hcl
test "$(incus storage get default source)" = polarita_zfs/data/incus/pool
install -d /etc/polarita
nft -c -f "$src/zones.nft"
install -m 644 "$src/zones.nft" /etc/polarita/zones.nft
install -m 644 "$src/polarita-zones.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-zones.service
systemctl start polarita-zones.service
nft -f /etc/polarita/zones.nft
install -m 644 "$src/zones.tf" zones.tf
tofu fmt -check
tofu init -input=false -lockfile=readonly
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
# Sdílený pracovní adresář může obsahovat i jiné služby. Nesmí dojít k jejich změně.
tofu show -json "$plan" | python3 -c '
import json, sys
for resource in json.load(sys.stdin).get("resource_changes", []):
    actions = resource["change"]["actions"]
    if actions in (["no-op"], ["read"]):
        continue
    if resource["address"].startswith(("incus_network.zone[", "incus_profile.zone[")) and actions == ["create"]:
        continue
    sys.exit("Neočekávaná změna: " + resource["address"])
'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
