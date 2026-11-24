#!/bin/bash
# Během skenování dovol odložit neaktivní stránky týmových služeb pouze do RAM.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
# Na větší VM či při odlišném swapu se použijí původní limity prostředí.
awk 'NR>1 && $1 !~ /^\/dev\/zram[0-9]+$/ {other=1} END {exit (NR<2 || other)}' /proc/swaps || exit 0
for setting in zulip-test:536870912 paperclip-test:268435456 paperless-test:268435456; do
    name=${setting%:*}
    limit=${setting#*:}
    path="/sys/fs/cgroup/lxc.payload.$name/memory.swap.max"
    [[ -e $path ]] || continue
    [[ $(incus config get "$name" user.polarita.role) == "$name" ]]
    # Zachovej vlastní limit správce. Nula je výchozí limit předchozí instalace.
    [[ $(cat "$path") == 0 ]] || continue
    [[ -z $(incus config get "$name" limits.memory.swap) ]] || continue
    printf '%s\n' "$limit" >"$path"
done
