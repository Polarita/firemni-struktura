#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/openbao-test
install -d -m 0750 "$work/tofu" "$work/bin"
exec 9>"$work/.install-lock"
flock 9
bash "$src/obraz.sh"
cd "$work/tofu"
install -m 0644 "$src/trezor.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tofu init -input=false -lockfile=readonly
tofu validate
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    actions = r["change"]["actions"]
    if actions in (["read"], ["no-op"]): continue
    if r["address"] in {"incus_instance.trezor", "incus_storage_volume.trezor"} and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna: " + r["address"])
'
tofu apply -input=false "$tmp/plan"
vm=openbao-test
actual=$(incus exec "$vm" -- sha256sum /usr/local/bin/bao)
[[ ${actual%% *} == "$(cat "$work/bao.sha256")" ]]
incus exec "$vm" -- install -d -m 0755 /etc/polarita-openbao
incus file push --mode 0644 "$src/server.hcl" "$vm/etc/polarita-openbao/server.hcl"
incus file push --mode 0644 "$src/openbao.service" "$vm/etc/systemd/system/openbao.service"
incus exec -T "$vm" -- bash -se < "$src/priprav-instanci.sh"
incus exec "$vm" -- cat /var/lib/polarita-openbao/tls/server.crt > "$work/ca.crt"
tofu plan -input=false -detailed-exitcode
[[ ! -e $work/uzamceno ]] || { echo 'Trezor je úmyslně uzamčen správcem.' >&2; exit 1; }
install -m 0755 "$1" "$work/bin/agent"
install -m 0755 "$src/start.sh" "$src/sprava.sh" "$work/bin/"
install -m 0644 "$src/agenti.py" "$src/pristupy.py" "$work/bin/"
if ! echo "$(cat "$work/bao.sha256")  $work/bin/bao" | sha256sum --check --status 2>/dev/null; then
    incus file pull "$vm/usr/local/bin/bao" "$tmp/bao"
    echo "$(cat "$work/bao.sha256")  $tmp/bao" | sha256sum --check --status
    install -m 0755 "$tmp/bao" "$work/bin/bao"
fi
install -m 0644 "$src"/polarita-openbao-{start,agenti}.{service,timer} /etc/systemd/system/
systemctl daemon-reload
bash "$src/klic.sh"
systemctl start polarita-openbao-start.service
systemctl enable --now polarita-openbao-start.timer
python3 "$work/bin/pristupy.py"
python3 "$work/bin/agenti.py" --install
systemctl enable --now polarita-openbao-agenti.timer
incus exec "$vm" -- test -s /var/lib/polarita-openbao/audit/pristupy.jsonl
snap=audit-$(date -u +%Y%m%d)
if ! incus storage volume snapshot show default openbao-test-raft "$snap" >/dev/null 2>&1; then
    incus storage volume snapshot create default openbao-test-raft "$snap" --expiry 7d
fi
