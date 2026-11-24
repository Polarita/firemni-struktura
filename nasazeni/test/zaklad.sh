#!/bin/bash
# První zavedení připraví pouze VM a disk označené vnějším instalátorem.
set -euo pipefail
umask 077
[[ $EUID == 0 && $(hostname -s) == ejpovice ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/lock/polarita-zaklad-systemu.lock
flock 8
bash "$src/vm.sh"
inc=(incus --project polarita)
guest=("${inc[@]}" exec -T polarita-hq --)
if [[ $("${inc[@]}" config get polarita-hq user.polarita.zalozeni) != instalator-test ]]; then
    python3 "$src/inventura.py"
    exit 0
fi
owner=$("${inc[@]}" config get polarita-hq volatile.uuid)
[[ $owner =~ ^[0-9a-f-]{36}$ && $("${inc[@]}" storage volume get zrcadlo polarita-hq-data user.polarita.vm) == "$owner" ]]
if [[ $("${inc[@]}" config get polarita-hq user.polarita.zaklad) == "$owner" ]]; then
    python3 "$src/inventura.py"
    exit 0
fi
incus query "/1.0/storage-pools/zrcadlo/volumes/custom/polarita-hq-data?project=polarita" | python3 -c '
import json,sys
v=json.load(sys.stdin)
if v["content_type"] != "block" or v["used_by"] != ["/1.0/instances/polarita-hq?project=polarita"]:
    sys.exit("Datový disk není vyhrazen pouze této VM")'
dst=/usr/local/lib/polarita-zaklad
"${guest[@]}" install -d -m 0755 "$dst"
for file in material.sh uloziste.sh start polarita-zfs.service system.sh; do
    "${inc[@]}" file push --mode 0644 "$src/zaklad/$file" "polarita-hq$dst/$file"
done
bash "$src/trezor/prijemce.sh" --pouze-prijemce
keys=/etc/polarita-test-obnova
"${inc[@]}" file push --mode 0644 "$keys/test.crt" "polarita-hq$dst/prijemce.crt"
"${guest[@]}" bash "$dst/system.sh" "$owner"
"${guest[@]}" bash "$dst/material.sh" /etc/polarita/zfs "$dst/prijemce.crt"
archive="$keys/zfs-$owner.cms"
next=$(mktemp -p "$keys" .zfs.XXXXXXXX)
trap 'rm -f -- "$next"' EXIT
"${guest[@]}" cat /etc/polarita/zfs/obnova.cms > "$next"
if [[ -e $archive ]]; then cmp "$next" "$archive"; else mv -T "$next" "$archive"; fi
decrypt() { openssl cms -decrypt -binary -inform DER -recip "$keys/test.crt" -inkey "$keys/test.key" -in "$archive"; }
decrypt | "${guest[@]}" bash -ec 'cmp -s - <(systemd-creds decrypt --name=polarita-zfs.key /etc/polarita/zfs/vtpm.cred -)'
"${guest[@]}" systemd-run --quiet --pipe --wait --collect \
    -p LoadCredentialEncrypted=polarita-zfs.key:/etc/polarita/zfs/vtpm.cred \
    bash "$dst/uloziste.sh" "$owner"
decrypt | "${guest[@]}" zfs load-key -n -L file:///dev/stdin polarita_zfs
"${guest[@]}" bash -ec '
    dst=$1
    zpool get -Ho value guid polarita_zfs >/etc/polarita/zfs/guid.next
    mv -T /etc/polarita/zfs/guid.next /etc/polarita/zfs/guid
    install -m 0755 "$dst/start" /etc/polarita/zfs/start
    install -m 0644 "$dst/polarita-zfs.service" /etc/systemd/system/polarita-zfs.service
    systemctl daemon-reload
    systemctl enable --now polarita-zfs.service
    zpool sync polarita_zfs
' -- "$dst"
snaps=$("${inc[@]}" snapshot list polarita-hq -f csv -c n)
if ! grep -Fxq test-zaklad <<<"$snaps"; then "${inc[@]}" snapshot create polarita-hq test-zaklad; fi
old_boot=$("${guest[@]}" cat /proc/sys/kernel/random/boot_id)
"${guest[@]}" systemctl reboot --no-block
for i in {1..120}; do
    if boot=$(timeout 4 "${guest[@]}" cat /proc/sys/kernel/random/boot_id 2>/dev/null) && [[ -n $boot && $boot != "$old_boot" ]] &&
        "${guest[@]}" systemctl is-active --quiet polarita-zfs.service; then break; fi
    sleep 3
done
[[ -n ${boot:-} && $boot != "$old_boot" ]]
python3 "$src/inventura.py"
"${inc[@]}" config set polarita-hq "user.polarita.zaklad=$owner"
