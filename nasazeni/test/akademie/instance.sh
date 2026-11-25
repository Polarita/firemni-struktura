#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/akademie-test/tofu
image=d0d7a11ddd2bd37705d805d2c34ffd6904bf4c06937adb4c31fb297b1685a468
install -dm0755 "$work" /srv/polarita/apps/akademie-test
install -d -m0750 /srv/polarita/data/akademie-test
# Vlastnictví adresáře moodledata přebírá www-data v posunutém mapování kontejneru.
mkdir -p /srv/polarita/data/akademie-test/moodledata
cd "$work"
exec 9>.instalace
flock 9
exec 8>/run/polarita-test-zatez.lock
flock 8
if ! incus image info "local:$image" >/dev/null 2>&1; then
    incus image copy "images:$image" local: --alias polarita-akademie-debian-20261118
fi
install -m0644 "$src/akademie.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
export TF_VAR_obraz=$image
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f -- "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for resource in json.load(sys.stdin).get("resource_changes", []):
    if (resource["address"] != "incus_instance.akademie" or
            resource["change"]["actions"] not in (["no-op"], ["read"], ["create"], ["update"])):
        sys.exit("Neočekávaná změna v plánu Akademie: " + resource["address"])'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
[[ $(incus config get akademie-test volatile.base_image) == "$image" ]]
incus exec -T akademie-test -- sh -ec '
    . /etc/os-release
    test "$ID:$VERSION_CODENAME" = debian:trixie
    chown www-data:www-data /var/lib/polarita-akademie
    chmod 0700 /var/lib/polarita-akademie
    mountpoint -q /var/lib/polarita-akademie
    findmnt -T /opt/polarita-akademie -no OPTIONS | tr , "\n" | grep -Fxq ro
    echo "Kontejner Akademie běží v síti app_internal nad Debianem 13."
'
