#!/bin/bash
# Během skenování dovol odložit neaktivní stránky týmových služeb pouze do RAM.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
# Na větší VM či při odlišném swapu se použijí původní limity prostředí.
awk 'NR>1 && $1 !~ /^\/dev\/zram[0-9]+$/ {other=1} END {exit (NR<2 || other)}' /proc/swaps || exit 0
zulip_limit=536870912
if awk '/^MemTotal:/ {small = $2 < 7 * 1024 * 1024}
         /^SwapFree:/ {free = $2 >= 512 * 1024} END {exit !(small && free)}' /proc/meminfo; then
    zulip_limit=805306368
fi
for setting in "zulip-test:$zulip_limit" paperclip-test:268435456 paperless-test:268435456; do
    name=${setting%:*}
    limit=${setting#*:}
    path="/sys/fs/cgroup/lxc.payload.$name/memory.swap.max"
    [[ -e $path ]] || continue
    [[ $(incus config get "$name" user.polarita.role) == "$name" ]]
    # Zvyšuj pouze výchozí nulu nebo dřívější limit 512 MiB spravovaný tímto skriptem.
    current=$(cat "$path")
    if [[ $current != 0 ]]; then
        [[ $name == zulip-test && $current == 536870912 && $limit == 805306368 ]] || continue
    fi
    [[ -z $(incus config get "$name" limits.memory.swap) ]] || continue
    printf '%s\n' "$limit" >"$path"
done
