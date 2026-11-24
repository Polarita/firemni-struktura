#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/karantena-test
store=/srv/polarita/data/clamav-db
[[ $(findmnt -n -o SOURCE -T "$store") == polarita_zfs/data/clamav-db ]]
install -d -m 0755 "$store/test"
install -d -m 0750 "$work/aktualizace"
exec 9>"$work/.signatury"
flock 9
digest=ed2ee243029c1f3c2e13c1eadd835fbca239bbbb80bbde06627f7676a17314f2
alias=polarita-clamav-db-1.5.4
if ! incus image info "$alias" >/dev/null 2>&1; then
    incus image copy "docker:clamav/clamav@sha256:$digest" local: --alias "$alias"
fi
incus image info "$alias" | grep -Fq "id: clamav/clamav@sha256:$digest"
cd "$work/aktualizace"
install -m 0644 "$src/updater.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
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
    if r["address"] == "incus_instance.signatury" and a in (["create"],["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
vm=clamav-signatury-test
incus exec -T "$vm" -- sh -ec '
ip -4 addr show dev eth0 | grep -q "10.239.31.13/"
getent hosts database.clamav.net | grep -Fq "10.239.31.1"
chown clamav:clamav /data/polarita-db
for name in main daily bytecode; do
    if test -s "/data/polarita-db/$name.cvd" || test -s "/data/polarita-db/$name.cld"; then continue; fi
    for f in "/var/lib/clamav/$name.cvd" "/var/lib/clamav/$name.cld"; do
        if test -s "$f"; then cp "$f" "/data/polarita-db/${f##*/}.next"; chown clamav:clamav "/data/polarita-db/${f##*/}.next"; chmod 0644 "/data/polarita-db/${f##*/}.next"; mv "/data/polarita-db/${f##*/}.next" "/data/polarita-db/${f##*/}"; break; fi
    done
done
for f in /var/lib/clamav/*.sign; do
    test -f "$f" || continue
    dst=/data/polarita-db/${f##*/}
    if test ! -e "$dst"; then cp "$f" "$dst.next"; chown clamav:clamav "$dst.next"; chmod 0644 "$dst.next"; mv "$dst.next" "$dst"; fi
done'
incus file push --mode=0644 "$src/freshclam.conf" "$vm/etc/clamav/polarita-freshclam.conf"
install -m 0755 "$src/aktualizuj.sh" "$work/aktualizuj.sh"
install -m 0644 "$src"/polarita-clamav-signatury.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-clamav-signatury.timer
systemctl start polarita-clamav-signatury.service
tofu plan -input=false -detailed-exitcode
