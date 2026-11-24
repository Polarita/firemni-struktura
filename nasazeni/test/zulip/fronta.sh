#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-fronta-test
store=/srv/polarita/data/zulip
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/data) == polarita_zfs/data ]]
if ! zfs list -Ho name polarita_zfs/data/zulip >/dev/null 2>&1; then
    [[ ! -e $store ]]
    zfs create -o mountpoint="$store" -o setuid=off -o devices=off polarita_zfs/data/zulip
fi
[[ $(findmnt -n -o SOURCE --mountpoint "$store") == polarita_zfs/data/zulip ]]
[[ $(zfs get -Ho value encryptionroot polarita_zfs/data/zulip) == polarita_zfs ]]
install -d "$store/fronta" /etc/polarita
nft -c -f "$src/fronta.nft"
install -m 0644 "$src/fronta.nft" /etc/polarita/zulip-fronta.nft
install -m 0644 "$src/polarita-zulip-fronta-sit.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-zulip-fronta-sit.service
systemctl restart polarita-zulip-fronta-sit.service
cd "$work/tofu"
install -m 0644 "$src/fronta.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
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
    if change["address"] == "incus_instance.fronta" and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + change["address"])'
tofu apply -input=false "$tmp/plan"
inside=(incus exec -T zulip-fronta-test --)
"${inside[@]}" bash -ec 'for i in {1..60}; do if test -S /run/systemd/private && mountpoint -q /var/lib/rabbitmq; then exit 0; fi; sleep 1; done; exit 1'
# Erlang při startu respektuje omezení malého testovacího serveru.
"${inside[@]}" install -d /etc/rabbitmq
"${inside[@]}" sh -c 'cat >/etc/rabbitmq/rabbitmq-env.conf' <<'CONF'
SERVER_ADDITIONAL_ERL_ARGS="+S 1:1 +A 4 +SDio 1 +SDcpu 1"
CTL_ERL_ARGS="+S 1:1 +A 2"
CONF
bash "$src/../incus/balicky.sh" zulip-fronta-test rabbitmq-server=4.0.5-10ubuntu5.2 \
    memcached=1.6.40-1ubuntu0.3 sasl2-bin=2.1.28+dfsg1-9ubuntu3 libsasl2-modules=2.1.28+dfsg1-9ubuntu3
"${inside[@]}" rabbitmq-diagnostics -q ping
"${inside[@]}" systemctl is-active memcached
tofu plan -input=false -detailed-exitcode
