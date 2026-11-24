#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
host=${1:?Chybí jméno ředitelství}
[[ $host =~ ^[a-z0-9.-]+\.ts\.net$ ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/paperless-test
data=/srv/polarita/data/paperless-test
dataset=polarita_zfs/data/paperless-test
bash "$src/zdroje.sh"
install -dm0755 "$work/conf" "$work/tofu"
exec 9>"$work/.instalace"
flock 9
# Rozbalení kořenového disku a zkouška OCR sdílejí I/O s běhy Chromium a karantény.
exec 8>/run/polarita-test-zatez.lock
flock 8
# OCI vlastní /etc/hosts připojuje zvenčí. Incus připojí čitelnou tabulku už při startu.
hostsfile="$work/conf/hosts"
printf '127.0.0.1 localhost\n127.0.1.1 paperless-test\n::1 localhost ip6-localhost ip6-loopback\n10.239.32.13 %s\n' "$host" >"$hostsfile.next"
chmod 0644 "$hostsfile.next"
if cmp -s "$hostsfile.next" "$hostsfile"; then rm "$hostsfile.next"; else mv -T "$hostsfile.next" "$hostsfile"; fi
[[ $(findmnt -no SOURCE --mountpoint /srv/polarita/data) == polarita_zfs/data ]]
if ! zfs list -Ho name "$dataset" >/dev/null 2>&1; then
    [[ ! -e $data ]]
    zfs create -o mountpoint="$data" -o devices=off -o setuid=off -o exec=off "$dataset"
fi
[[ $(findmnt -no SOURCE --mountpoint "$data") == "$dataset" ]]
[[ $(zfs get -Ho value encryptionroot "$dataset") == polarita_zfs ]]
for dir in aplikace fronta socket; do
    if [[ ! -d $data/$dir ]]; then install -dm0750 "$data/$dir"; fi
done
# Připojený kořen musí zpřístupnit podadresáře účtu paperless (UID/GID 1000).
# Posun identit na disku Incusu mapuje skupinu 1000 do stejné skupiny v kontejneru.
chgrp 1000 "$data/aplikace"
chmod 0750 "$data/aplikace"
install -m0755 "$src/start.sh" "$src/broker.sh" "$work/conf/"
install -m0644 "$src/ocr.py" "$work/conf/"
cd "$work/tofu"
install -m0644 "$src/paperless.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
fingerprint() {
    incus query "/1.0/images/aliases/$1" | python3 -c 'import json,re,sys; s=json.load(sys.stdin)["target"]; assert re.fullmatch("[a-f0-9]{64}",s); print(s)'
}
export TF_VAR_image TF_VAR_broker_image
TF_VAR_image=$(fingerprint polarita-paperless-3.5.1)
TF_VAR_broker_image=$(fingerprint polarita-valkey-9.2.0)
[[ $(incus image get-property "$TF_VAR_broker_image" id) == valkey/valkey@sha256:084a129b7e05269af288ddc9bc1a57eb9d1e3c879fd8cf2a28566187234f2693 ]]
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for item in json.load(sys.stdin).get("resource_changes",[]):
    actions=item["change"]["actions"]
    if actions in (["no-op"],["read"]): continue
    if item["address"] not in {"incus_instance.archiv","incus_instance.fronta"} or actions not in (["create"],["update"]):
        sys.exit("Neočekávaná změna "+item["address"])'
tofu apply -parallelism=1 -input=false "$plan"
incus exec -T paperless-fronta-test -- sh -ec '
    for n in $(seq 1 60); do [ -S /run/paperless-broker/valkey.sock ] && break; sleep 1; done
    test "$(valkey-cli -s /run/paperless-broker/valkey.sock PING)" = PONG
    test "$(valkey-cli --raw -s /run/paperless-broker/valkey.sock CONFIG GET port | tail -1)" = 0
'
incus exec -T paperless-test --user 1000 --group 1000 -- python3 -c '
import socket
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(5)
    s.connect("/run/paperless-broker/valkey.sock")
    s.sendall(b"*1\r\n$4\r\nPING\r\n")
    assert s.makefile("rb").readline() == b"+PONG\r\n"
print("Účet Paperless dosáhl na svou frontu přes unixový socket.")'
incus exec -T paperless-test --user 1000 --group 1000 -- test -x /var/lib/polarita-paperless
incus exec -T paperless-test --user 1000 --group 1000 -- python3 /etc/polarita-paperless/ocr.py
tofu plan -input=false -detailed-exitcode
