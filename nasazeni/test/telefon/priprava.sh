#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
base=/srv/polarita/infra/asterisk-test
install -dm0750 "$base/tofu"
exec 9>"$base/.priprava"
flock 9
cd "$base/tofu"
install -m0644 "$src/asterisk.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f -- "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import sys,json
for r in json.load(sys.stdin).get("resource_changes", []):
    if r["address"] != "incus_instance.asterisk" or r["change"]["actions"] not in (["no-op"], ["create"], ["update"]):
        sys.exit("Neočekávaná změna při přípravě ústředny v TEST.")
'
tofu apply -input=false "$plan"
inside=(incus exec -T asterisk-test --)
"${inside[@]}" timeout 90 sh -ec 'until test -S /run/systemd/private; do sleep 1; done'
"${inside[@]}" python3 -c 'import socket; assert [n for _, n in socket.if_nameindex()] == ["lo"]'
# Balíčková výchozí konfigurace se nesmí spustit před zavedením konfigurace TEST.
"${inside[@]}" systemctl mask asterisk.service
bash "$src/../incus/balicky.sh" asterisk-test 'asterisk=1:22.5.2~dfsg+~cs6.15.60671435-1'
"${inside[@]}" /usr/sbin/asterisk -V
