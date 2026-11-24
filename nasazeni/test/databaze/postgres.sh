#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
bash "$src/obraz.sh"
work=/srv/polarita/infra/postgres-test
install -d -m 0750 "$work/tofu"
exec 8>"$work/.instalace"
flock 8
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/data/postgres) == polarita_zfs/data/postgres ]]
[[ $(zfs get -Hp -o value recordsize polarita_zfs/data/postgres) == 8192 ]]
[[ $(zfs get -H -o value keystatus polarita_zfs/data/postgres) == available ]]
install -d -m 0750 /srv/polarita/data/postgres/test
cd "$work/tofu"
export TF_VAR_postgres_image=local:polarita-postgres-test-$(sha256sum "$src/postgres.lock.json" | cut -c1-16)
install -m 0644 "$src/postgres.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
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
    if r["address"] == "incus_instance.postgres" and a in (["create"],["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
incus exec -T postgres-test -- bash -ec 'for i in {1..60}; do if mountpoint -q /run && test -S /run/systemd/private && ip -4 -o addr show dev eth0 | grep -q "10.239.33.12/"; then exit 0; fi; sleep 1; done; exit 1'
incus exec -T postgres-test -- bash -se <"$src/konfigurace.sh"
incus file pull postgres-test/var/lib/polarita-postgres/pki/server.crt "$work/ca.crt"
tofu plan -input=false -detailed-exitcode
