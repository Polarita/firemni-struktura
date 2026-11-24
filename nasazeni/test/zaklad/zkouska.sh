#!/bin/bash
# Syntetický klíč a souborové zařízení pro zkoušku vytvoření, opakování, importu a obnovy.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
umask 077
src=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d /var/tmp/polarita-zfs-test.XXXXXXXX)
ram=$(mktemp -d -p /run polarita-zkouska-klice.XXXXXXXX)
pool=polarita_test_${tmp##*.}
owner=$(cat /proc/sys/kernel/random/uuid)
cleanup() {
    if zpool list -H -o name "$pool" >/dev/null 2>&1; then
        if [[ $(zfs get -Ho value cz.polarita:vm "$pool") != "$owner" ]]; then return 1; fi
        zpool export "$pool" || return 1
    fi
    rm -rf -- "$tmp" "$ram"
}
trap cleanup EXIT
truncate -s 256M "$tmp/disk"
openssl req -x509 -newkey rsa:3072 -nodes -subj /CN=Polarita-TEST-zkouska -days 1 \
    -keyout "$ram/zkouska.key" -out "$tmp/zkouska.crt" >/dev/null 2>&1
bash "$src/material.sh" "$tmp/obalka" "$tmp/zkouska.crt"
bash "$src/material.sh" "$tmp/obalka" "$tmp/zkouska.crt"
apply() {
    systemd-run --quiet --pipe --wait --collect \
        -p "LoadCredentialEncrypted=polarita-zfs.key:$tmp/obalka/vtpm.cred" bash "$src/uloziste.sh" "$owner" "$tmp"
}
# Rozpoznatelný oddíl z jiné instalace se nesmí přepsat.
mkfs.ext4 -F -q "$tmp/disk"
before=$(blkid -p -o value -s UUID "$tmp/disk")
if apply; then echo 'Instalátor přepsal cizí systém souborů.' >&2; exit 1; fi
[[ -n $before && $(blkid -p -o value -s UUID "$tmp/disk") == "$before" ]]
echo 'Existující souborový systém zůstal beze změn.'
mv "$tmp/disk" "$tmp/cizi-disk"
truncate -s 256M "$tmp/disk"
printf 'zachovat' | dd of="$tmp/disk" bs=1 seek=73400320 conv=notrunc status=none
if apply; then echo 'Instalátor přepsal data bez souborového systému.' >&2; exit 1; fi
[[ $(dd if="$tmp/disk" bs=1 skip=73400320 count=8 status=none) == zachovat ]]
echo 'Zdroj bez signatury zachoval původní data uprostřed zařízení.'
mv "$tmp/disk" "$tmp/data-bez-signatury"
truncate -s 256M "$tmp/disk"
apply
guid=$(zpool get -Ho value guid "$pool")
printf '%s\n' "$owner" >"$tmp/data/workspace/vzorek"
apply
zpool export "$pool"
apply
[[ $(zpool get -Ho value guid "$pool") == "$guid" && $(cat "$tmp/data/workspace/vzorek") == "$owner" ]]
openssl cms -decrypt -binary -inform DER -inkey "$ram/zkouska.key" -recip "$tmp/zkouska.crt" -in "$tmp/obalka/obnova.cms" |
    zfs load-key -n -L file:///dev/stdin "$pool"
echo 'ZFS ověřil nezávislou obnovovací obálku. Po opakované instalaci a importu zůstaly shodné GUID i vzorová data.'
