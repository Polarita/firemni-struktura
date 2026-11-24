#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=90 install --yes --no-install-recommends sanoid=2.3.0-1
install -d /etc/sanoid/polarita-test
install -m 0644 "$src/sanoid.conf" /etc/sanoid/polarita-test/
install -m 0644 "$src"/polarita-sanoid.{timer,service} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-sanoid.timer
systemctl start polarita-sanoid.service
systemctl is-active --quiet polarita-sanoid.timer
for dataset in vault data/{postgres,vaultwarden,gitea,legal-archive/test}; do
    # Zkontroluj skutečně vytvořený často pořizovaný snímek každého datasetu.
    name=$(zfs list -H -d 1 -t snapshot -o name -s creation "polarita_zfs/$dataset" | awk '/@autosnap_.*_frequently$/ {s=$0} END {print s}')
    [[ $name == "polarita_zfs/$dataset@autosnap_"* ]]
    if [[ $dataset == vault ]]; then source_snapshot=$name; fi
done
mount=$(mktemp -d /run/polarita-sanoid-obnova-XXXXXXXX)
child="polarita_zfs/sanoid-obnova-${mount##*-}"
start=$(date +%s%N)
zfs clone -o readonly=on -o mountpoint="$mount" "$source_snapshot" "$child" || { rmdir "$mount"; exit 1; }
trap 'zfs destroy "$child"; rmdir "$mount" 2>/dev/null || true' EXIT
origin="/srv/polarita/vault/.zfs/snapshot/${source_snapshot#*@}"
expected=$(git -c safe.directory="$origin" -C "$origin" rev-parse HEAD)
actual=$(git -c safe.directory="$mount" -C "$mount" rev-parse HEAD)
[[ $actual == "$expected" ]]
git -c safe.directory="$mount" -C "$mount" fsck --full --strict >/dev/null
echo "Sanoid vytvořil snímky pěti datasetů. Historie znalostního repozitáře byla zpřístupněna a ověřena v klonu pouze pro čtení za $((($(date +%s%N)-start)/1000000)) ms."
