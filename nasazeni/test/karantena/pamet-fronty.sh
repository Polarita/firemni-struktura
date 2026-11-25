#!/bin/bash
# Týmové aplikace mohou odkládat neaktivní stránky do komprimované RAM ředitelství.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
awk 'NR>1 && $1 !~ /^\/dev\/zram[0-9]+$/ {other=1} END {exit (NR<2 || other)}' /proc/swaps || exit 0
zulip=512
paperclip=256
paperless=256
umami=0
if awk '/^MemTotal:/ {small = $2 < 7 * 1024 * 1024}
        /^SwapFree:/ {free = $2 >= 512 * 1024} END {exit !(small && free)}' /proc/meminfo; then
    zulip=768
    # Při dostatku volné zram mohou služby uvolnit více místa pro soubory z Ceph.
    if awk '/^SwapFree:/ {exit !($2 >= 1024 * 1024)}' /proc/meminfo; then
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
