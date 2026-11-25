#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/medusa-test
bash "$src/node.sh"
install -dm0755 "$work/tofu" /srv/polarita/apps/medusa-test
exec 9>"$work/.instalace"
flock 9
cd "$work/tofu"
install -m0644 "$src/medusa.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f -- "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes",[]):
    actions=r["change"]["actions"]
    if actions in (["no-op"],["read"]): continue
    if r["address"] != "incus_instance.medusa" or actions not in (["create"],["update"]):
        sys.exit("Neočekávaná změna "+r["address"])'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
incus exec -T medusa-test -- /opt/node/bin/node --version
