#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/mx-test
install -d -m 0755 "$work/conf"
cd "$work"
exec 9>".install.lock"
flock 9
install -m 0644 "$src/incus/providers.tf" "$src/incus/.terraform.lock.hcl" "$src/mx/mx.tf" .
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cli=stalwart-cli-x86_64-unknown-linux-musl
archive_sum=25ab98bd38a79f1a6cd73db9a1f143807211a47f11142303cb422f2ab85f7f9e
binary_sum=75ae4eee19c9e9f9742ee047f4faf6a1ff60377bc9dac4776dd3dd8168a697f4
if [[ ! -x conf/stalwart-cli ]] || ! echo "$binary_sum  conf/stalwart-cli" | sha256sum --check --status; then
    curl -fsSL --retry 3 "https://github.com/stalwartlabs/cli/releases/download/v2.0.0/$cli.tar.xz" -o "$tmp/cli.tar.xz"
    echo "$archive_sum  $tmp/cli.tar.xz" | sha256sum -c -
    tar -xf "$tmp/cli.tar.xz" -C "$tmp" "$cli/stalwart-cli"
    echo "$binary_sum  $tmp/$cli/stalwart-cli" | sha256sum -c -
    install -m 0755 "$tmp/$cli/stalwart-cli" conf/stalwart-cli.next
    mv -f conf/stalwart-cli.next conf/stalwart-cli
fi
for file in start.sh plan.ndjson config.json; do
    install -m 0644 "$src/mx/$file" "conf/$file.next"
    mv -f "conf/$file.next" "conf/$file"
done
tofu fmt -check
tofu init -input=false -lockfile=readonly
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json, sys
for item in json.load(sys.stdin).get("resource_changes", []):
    actions = item["change"]["actions"]
    if actions in (["no-op"], ["read"]): continue
    if item["address"] in {"incus_instance.mx","incus_storage_volume.mx"} and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna: " + item["address"])
'
existing=false
if incus info stalwart-mx-test >/dev/null 2>&1; then existing=true; fi
tofu apply -input=false "$tmp/plan"
digest=$(sha256sum conf/* | sha256sum)
state=$(incus query /1.0/instances/stalwart-mx-test/state | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
if [[ $state == Stopped ]]; then
    incus start stalwart-mx-test
elif [[ $state != Running ]]; then
    echo "Neočekávaný stav SMTP kontejneru: $state" >&2
    exit 1
elif "$existing" && { [[ ! -f .applied || $(cat .applied) != "$digest" ]] ||
    ! incus exec stalwart-mx-test -- openssl x509 -checkend 604800 -noout -in /var/lib/stalwart/tls/mx.crt >/dev/null; }; then
    incus restart stalwart-mx-test
fi
incus exec stalwart-mx-test --user 0 --group 0 -- chown stalwart:stalwart /var/lib/stalwart
python3 "$src/mx/zkouska.py"
printf '%s\n' "$digest" >.applied
tofu plan -input=false -detailed-exitcode
