#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/umami-test
bash "$src/obraz.sh"
install -dm0755 "$work/conf" "$work/tofu"
exec 9>"$work/.instalace"
flock 9
reload="$work/.obnovit-start"
if [[ -f $work/conf/start.sh ]] && ! cmp -s "$src/start.sh" "$work/conf/start.sh"; then touch "$reload"; fi
install -m0644 "$src/db-host.sh" "$work/conf/db-host.sh"
install -m0755 "$src/start.sh" "$work/conf/start.sh"
install -m0644 "$src/over.mjs" "$work/conf/over.mjs"
incus file pull postgres-test/var/lib/polarita-postgres/pki/server.crt "$work/conf/postgres.next"
chmod 0644 "$work/conf/postgres.next"
mv -T "$work/conf/postgres.next" "$work/conf/postgres.crt"
cd "$work/tofu"
install -m0644 "$src/umami.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
export TF_VAR_image
TF_VAR_image=$(incus query /1.0/images/aliases/polarita-umami-3.5.0 | python3 -c 'import json,re,sys; s=json.load(sys.stdin)["target"]; assert re.fullmatch("[0-9a-f]{64}",s); print(s)')
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f -- "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes",[]):
    a=r["change"]["actions"]
    if a in (["no-op"],["read"]): continue
    if r["address"]!="incus_instance.umami" or a not in (["create"],["update"]): sys.exit("Neočekávaná změna "+r["address"])'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
if [[ -f $reload ]]; then
    [[ $(incus config get umami-test user.polarita.role) == umami-test ]]
    incus restart umami-test
    rm -f -- "$reload"
fi
