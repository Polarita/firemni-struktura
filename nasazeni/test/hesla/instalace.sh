#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
domain=${1:?HTTPS adresa trezoru}
[[ $domain =~ ^https://[a-z0-9.-]+/hesla$ ]]
work=/srv/polarita/infra/vaultwarden-test
data=/srv/polarita/data/vaultwarden
[[ $(findmnt -n -o SOURCE --mountpoint "$data") == polarita_zfs/data/vaultwarden ]]
[[ $(zfs get -H -o value keystatus polarita_zfs/data/vaultwarden) == available ]]
install -d -m 0700 "$data/test"
install -d -m 0750 "$work/tofu"
exec 9>"$work/.lock"
flock 9
digest=4fe17f415f90087377d37c755e0ea3cf189dcc6794e49cdd2a9adbb4937d9e1f
alias=polarita-vaultwarden-test-1.37.5
if ! incus image info "$alias" >/dev/null 2>&1; then
    incus image copy "docker:vaultwarden/server@sha256:$digest" local: --alias "$alias"
fi
incus image info "$alias" | grep -Fx 'Fingerprint: 6141c4009e3d7012a2faa1ac6f371f0a06b420ecca2880403377afc15f0e6824'
cd "$work/tofu"
export TF_VAR_vaultwarden_url="$domain"
install -m 0644 "$src/vaultwarden.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
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
    if r["address"] == "incus_instance.hesla" and a in (["create"],["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
for i in {1..45}; do
    if curl --noproxy '*' -fsS --max-time 2 http://10.239.33.11:8080/hesla/alive >/dev/null; then break; fi
    sleep 1
done
curl --noproxy '*' -fsS http://10.239.33.11:8080/hesla/api/config | python3 -c '
import json,sys
c=json.load(sys.stdin)
assert c["environment"]["vault"] == sys.argv[1] and c["settings"]["disableUserRegistration"]
print("Vaultwarden odpověděl na vlastní adrese; veřejná registrace je vypnuta.")' "$domain"
if ! python3 -c 'import cryptography, argon2' 2>/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends python3-cryptography python3-argon2
fi
python3 "$src/ucet.py"
tofu plan -input=false -detailed-exitcode
