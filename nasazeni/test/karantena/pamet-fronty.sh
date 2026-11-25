#!/bin/bash
# Týmové aplikace mohou odkládat neaktivní stránky do komprimované RAM ředitelství.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
# Vedle zram může existovat šifrovaná rezerva z instalátoru. Do volné zram ji nezapočítávej.
reserve=$(readlink -e /dev/mapper/poltestswap || true)
if [[ -n $reserve ]]; then
    sys=/sys/class/block/${reserve##*/}
    [[ $(cat "$sys/dm/uuid") == CRYPT-PLAIN-poltestswap ]] || exit 0
    [[ $(cat "$sys"/slaves/loop*/loop/backing_file) == /var/lib/polarita-test-swap/rezerva.img ]] || exit 0
fi
free_zram=$(awk -v reserve="$reserve" '
    NR == 1 {next}
    $1 ~ /^\/dev\/zram[0-9]+$/ {free += $3 - $4; found=1; if ($5 <= 10) low=1; next}
    reserve != "" && ($1 == reserve || $1 == "/dev/mapper/poltestswap") && $5 == 10 {disk=1; next}
    {other=1}
    END {if (!found || other || (disk && low)) exit 1; print free + 0}' /proc/swaps) || exit 0
zulip=512
paperclip=256
paperless=256
umami=0
if (( free_zram >= 512 * 1024 )) && awk '/^MemTotal:/ {exit !($2 < 7 * 1024 * 1024)}' /proc/meminfo; then
    zulip=768
    # Při dostatku volné zram mohou služby uvolnit více místa pro soubory z Ceph.
    if (( free_zram >= 1024 * 1024 )); then
        zulip=1024
        paperclip=384
        paperless=512
        umami=128
    fi
fi
for setting in "zulip-test:$zulip" "paperclip-test:$paperclip" "paperless-test:$paperless" "umami-test:$umami"; do
    name=${setting%:*}
    limit=$(( ${setting#*:} * 1024 * 1024 ))
    path="/sys/fs/cgroup/lxc.payload.$name/memory.swap.max"
    [[ -e $path ]] || continue
    current=$(cat "$path")
    [[ $current =~ ^[0-9]+$ && $current -lt $limit ]] || continue
    # Převezmi pouze výchozí nulu nebo hodnoty používané předchozím vydáním.
    case "$name:$current" in
        *:0|zulip-test:536870912|zulip-test:805306368|paperclip-test:268435456|paperless-test:268435456) ;;
        *) continue ;;
    esac
    [[ $(incus config get "$name" user.polarita.role) == "$name" ]]
    [[ -z $(incus config get "$name" limits.memory.swap) ]] || continue
    printf '%s\n' "$limit" >"$path"
done
