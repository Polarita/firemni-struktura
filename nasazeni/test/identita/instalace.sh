#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
url=${1:?HTTPS adresa identity}
[[ $url =~ ^https://[a-z0-9.-]+/identita$ ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/keycloak-test
install -d -m 0750 "$work"/{tofu,conf}
exec 9>"$work/.lock"
flock 9
install -m 0644 "$src/start.sh" /srv/polarita/infra/postgres-test/ca.crt "$work/conf/"
chmod 0755 "$work/conf"
install -d -m 0700 /srv/polarita/data/bootstrap-test/keycloak-test
python3 "$src/realm.py" "$url"
if ! incus image info polarita-keycloak-test-26.8.2 >/dev/null 2>&1; then
    if ! incus remote list -c n -f csv | grep -Fxq quay; then
        incus remote add quay https://quay.io --protocol=oci --public
    fi
    incus image copy quay:keycloak/keycloak@sha256:75b5c435a83b530caba5923922f93d47b2e3f8b4ad9e79200581122996653e55 local: --alias polarita-keycloak-test-26.8.2
fi
incus image info polarita-keycloak-test-26.8.2 | grep -Fx 'Fingerprint: e26c9eb621347b93b0d5e894df7c37f8d7710067628823cf917cf161cbe04769'
cd "$work/tofu"
export TF_VAR_identity_url="$url"
install -m 0644 "$src/keycloak.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
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
    if r["address"] == "incus_instance.identita" and a in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
