#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/garage-test
store=/srv/polarita/data/garage
[[ $(findmnt -n -o SOURCE --mountpoint "$store") == polarita_zfs/data/garage ]]
[[ $(zfs get -H -o value encryption polarita_zfs/data/garage) == aes-256-gcm ]]
install -d -m 0755 "$work/bin" "$work/tofu" "$store/test"
exec 9>"$work/.instalace"
flock 9
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
sha=2ff667286217cd73ebcb1c03af993822365000441dfe31a80cb64c5189a9dea8
if ! echo "$sha  $work/bin/garage-2.5.0" | sha256sum --check --status 2>/dev/null; then
    curl --fail --location --retry 3 --max-time 240 -o "$tmp/garage" https://garagehq.deuxfleurs.fr/_releases/v2.5.0/x86_64-unknown-linux-musl/garage
    echo "$sha  $tmp/garage" | sha256sum --check --status
    install -m 0755 "$tmp/garage" "$work/bin/garage-2.5.0"
fi
sha=a563843e11cbce39c557bd429ebb787d56f49d51d9bbb3292cd9b36b37a60cdf
if ! echo "$sha  $work/bin/caddy" | sha256sum --check --status 2>/dev/null; then
    incus file pull caddy-test/usr/bin/caddy "$tmp/caddy"
    echo "$sha  $tmp/caddy" | sha256sum --check --status
    install -m 0755 "$tmp/caddy" "$work/bin/caddy"
fi
cd "$work/tofu"
install -m 0644 "$src/garage.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
image=$(sed -nE 's/^ *image *= *"local:([[:xdigit:]]{64})"$/\1/p' "$src/garage.tf")
[[ $image =~ ^[0-9a-f]{64}$ ]]
if ! incus image info "$image" >/dev/null 2>&1; then incus image copy "images:$image" local:; fi
tofu init -input=false -lockfile=readonly
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    actions=r["change"]["actions"]
    if actions in (["no-op"], ["read"]): continue
    if r["address"] == "incus_instance.garage" and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$tmp/plan"
inside=(incus exec -T garage-test --)
"${inside[@]}" bash -ec '
for i in {1..60}; do if test -S /run/systemd/private; then break; fi; sleep 1; done
getent group garage-test >/dev/null || groupadd --system --gid 17306 garage-test
getent passwd garage-test >/dev/null || useradd --system --uid 17306 --gid garage-test --home-dir /var/lib/garage --shell /usr/sbin/nologin garage-test
[[ $(id -u garage-test) == 17306 && $(id -g garage-test) == 17306 ]]
mountpoint -q /var/lib/garage
install -d -m 0755 /etc/polarita-garage
install -d -m 0700 -o garage-test -g garage-test /var/lib/garage/{meta,data,caddy}
'
incus file push --mode=0644 "$src/garage.toml" "$src/Caddyfile" garage-test/etc/polarita-garage/
incus file push --mode=0644 "$src/garage-test.service" "$src/garage-tls.service" garage-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" /opt/garage/garage-2.5.0 --version
tofu plan -input=false -detailed-exitcode
incus file push --mode=0644 "$src/kose.py" garage-test/etc/polarita-garage/kose.py
if ! python3 -c 'import boto3,botocore' >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends install python3-boto3=1.40.72-1build1
fi
