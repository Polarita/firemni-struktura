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
inside=(incus exec -T medusa-test --)
"${inside[@]}" bash -ec '
    getent group medusa >/dev/null || groupadd --system --gid 17309 medusa
    id medusa >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin --uid 17309 --gid medusa medusa
    [[ $(id -u medusa) == 17309 && $(id -g medusa) == 17309 ]]
    install -dm0755 /etc/polarita-medusa
'
ca=$(mktemp)
trap 'rm -f -- "$plan" "$ca"' EXIT
incus file pull postgres-test/var/lib/polarita-postgres/pki/server.crt "$ca"
incus file push --mode=0644 "$ca" medusa-test/etc/polarita-medusa/.postgres.next
"${inside[@]}" mv -T /etc/polarita-medusa/.postgres.next /etc/polarita-medusa/postgres.crt
