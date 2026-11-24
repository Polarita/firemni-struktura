#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-test
export TF_VAR_fqdn=${1:?Chybí jméno testovacího ředitelství}
[[ $TF_VAR_fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
bash "$src/zdroje.sh"
bash "$src/klient-valkey.sh"
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/data/zulip) == polarita_zfs/data/zulip ]]
install -d -m 0750 "$work/tofu"
install -d -m 0755 /srv/polarita/data/zulip/aplikace
exec 9>"$work/.instance"
flock 9
running_update=false
if [[ $(incus list zulip-test --format csv -c s) == RUNNING ]] && ! cmp -s "$src/start.sh" "$work/conf/start.sh"; then
    running_update=true
fi
install -m 0644 "$src/start.sh" "$work/conf/"
install -m 0644 /srv/polarita/infra/postgres-test/ca.crt "$work/conf/postgres.crt"
TF_VAR_image=$(incus image list polarita-zulip-13.3-0 --format json | python3 -c 'import json,sys; (r,)=json.load(sys.stdin); print(r["fingerprint"])')
[[ $TF_VAR_image =~ ^[a-f0-9]{64}$ ]]
export TF_VAR_image
cd "$work/tofu"
install -m 0644 "$src/aplikace.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
bash "$src/../incus/tofu-init.sh"
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json, sys
for change in json.load(sys.stdin).get("resource_changes", []):
    actions = change["change"]["actions"]
    if actions in (["no-op"], ["read"]): continue
    if change["address"] == "incus_instance.chat" and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna "+change["address"])'
tofu apply -input=false "$tmp/plan"
if [[ $running_update == true ]]; then
    incus restart zulip-test
fi
incus exec -T zulip-test -- bash -ec '
cd /home/zulip/deployments/current
test -x manage.py && test -x /sbin/entrypoint.sh
# Po startu OCI může Incus přijmout exec ještě před dokončením obou instalací v entrypointu.
for attempt in {1..60}; do
    if sha256sum --status -c <<SUMS
addcc82d55a89680b0c9e3ccb50974d727753007a0e4cce20f5e1cdf751d7f42  zerver/lib/redis_utils.py
69f76653777b14a11665a4aaab16d3f61ab1d0a8566478374e7a1d5c325d47e4  zproject/backends.py
SUMS
    then exit 0; fi
    sleep 1
done
echo "Zulip nenačetl ověřené úpravy klienta Valkey" >&2
exit 1'
tofu plan -input=false -detailed-exitcode
