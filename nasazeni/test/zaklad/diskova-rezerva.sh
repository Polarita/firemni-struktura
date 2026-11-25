#!/bin/bash
# Nízká priorita ponechá běžné odkládání na ZRAM. Soubor leží na systémovém ext4 mimo ZFS.
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
dir=/var/lib/polarita-test-swap
file=$dir/rezerva.img
map=poltestswap
device=/dev/mapper/$map
exec 9>/run/polarita-swap-test.lock
flock 9
[[ $(findmnt -T /var/lib -n -o FSTYPE) == ext4 && ! -L $dir ]]
if [[ ! -d $dir ]]; then install -d -m0700 "$dir"; fi
[[ $(stat -c '%u:%g:%a' "$dir") == 0:0:700 ]]
line="$map $file /dev/urandom swap,cipher=aes-xts-plain64,size=256,nofail"
if [[ -e /etc/crypttab ]]; then
    [[ -f /etc/crypttab && ! -L /etc/crypttab ]]
    awk -v key="$map" -v file="$file" -v value="$line" '($1==key || $2==file) && $0!=value {exit 1}' /etc/crypttab
fi
# Před spuštěním generátoru se ověří, že název nepatří jinému zařízení.
backing() {
    local name loop
    name=$(basename "$(readlink -f "$device")")
    for loop in /sys/class/block/"$name"/slaves/loop*; do
        [[ -r $loop/loop/backing_file && $(cat "$loop/loop/backing_file") == "$file" ]] && return 0
    done
    return 1
}
if [[ -e $device ]]; then backing; fi
if [[ ! -e $file && ! -L $file ]]; then
    (( $(df -B1 --output=avail "$dir" | tail -1) >= 8 * 1024**3 ))
    umask 077
    tmp=$(mktemp "$dir/.rezerva-XXXXXX")
    trap 'rm -f -- "$tmp"' EXIT
    fallocate -l 2GiB "$tmp"
    mv -T "$tmp" "$file"
fi
[[ -f $file && ! -L $file && $(stat -c '%u:%g:%a:%h:%s' "$file") == 0:0:600:1:2147483648 ]]
if ! grep -Fqx -- "$line" /etc/crypttab 2>/dev/null; then
    (umask 077; printf '\n%s\n' "$line" >>/etc/crypttab)
fi
unit=dev-mapper-poltestswap.swap
next=$(mktemp /etc/systemd/system/.poltestswap-XXXXXX)
trap 'rm -f -- "$next"' EXIT
cat >"$next" <<'UNIT'
[Unit]
Description=Šifrovaná disková rezerva pro instalaci TEST
Requires=systemd-cryptsetup@poltestswap.service
After=systemd-cryptsetup@poltestswap.service
[Swap]
What=/dev/mapper/poltestswap
Priority=10
[Install]
WantedBy=swap.target
UNIT
target=/etc/systemd/system/$unit
if [[ -e $target ]]; then cmp "$next" "$target"; else chmod 0644 "$next"; mv -T "$next" "$target"; fi
if ! systemctl is-active --quiet "$unit" || ! systemctl is-enabled --quiet "$unit"; then
    systemctl daemon-reload
    systemctl enable --now "$unit"
fi
backing
awk -v dev="$(readlink -f "$device")" -v alias="$device" '($1==dev || $1==alias) && $3>2000000 && $5==10 {ok=1} END {exit !ok}' /proc/swaps
echo 'VM má ověřenou 2GiB šifrovanou diskovou rezervu s prioritou pod oběma zařízeními ZRAM.'
