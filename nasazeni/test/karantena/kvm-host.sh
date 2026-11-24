#!/bin/bash
# Nastavení linuxového hosta vnořené karantény se použije při startu polarita-hq.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
dest=/etc/default/grub.d/99-polarita-nested-kvm.cfg
line='GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX no-kvmapf"'
if [[ ! -f $dest ]] || [[ $(cat "$dest") != "$line" ]]; then
    printf '%s\n' "$line" > "$dest"
    update-grub
fi
grep -qE '^[[:space:]]*linux[[:space:]].* no-kvmapf( |$)' /boot/grub/grub.cfg
