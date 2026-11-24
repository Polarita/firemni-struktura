#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/valkey-test
install -d -m 0750 "$work/tofu" "$work/conf"
exec 9>"$work/.instalace"
flock 9
install -m 0644 "$src/start.sh" "$src/valkey.conf" "$work/conf/"
chmod 0755 "$work/conf"
digest=084a129b7e05269af288ddc9bc1a57eb9d1e3c879fd8cf2a28566187234f2693
alias=polarita-valkey-9.2.0
if ! incus image info "$alias" >/dev/null 2>&1; then
    incus image copy "docker:valkey/valkey@sha256:$digest" local: --alias "$alias"
fi
info=$(incus query "/1.0/images/aliases/$alias")
fingerprint=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["target"])' <<<"$info")
[[ $fingerprint =~ ^[0-9a-f]{64}$ ]]
[[ $(incus image get-property "$fingerprint" id) == "valkey/valkey@sha256:$digest" ]]
cd "$work/tofu"
install -m 0644 "$src/valkey.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
export TF_VAR_valkey_image="local:$fingerprint"
tofu init -input=false -lockfile=readonly
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    a = r["change"]["actions"]
    if a in (["no-op"], ["read"]): continue
    if r["address"] in {"incus_instance.valkey", "incus_storage_volume.valkey"} and a in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
incus exec -T valkey-test -- valkey-server --version
incus exec -T valkey-test -- sh -ec 'test "$(id -u valkey)" = 999; test "$(id -g valkey)" = 999'
