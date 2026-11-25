#!/bin/bash
# ZRAM vytvoří prostor pro neaktivní stránky při souběhu firemních služeb a CI na Ejpovicích.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm && $EUID == 0 ]]
memory=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
if (( memory >= 7 * 1024 * 1024 )); then exit 0; fi
if ! dpkg-query -W -f='${Status}' systemd-zram-generator 2>/dev/null | grep -qx 'install ok installed'; then
    DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 -y --no-install-recommends install systemd-zram-generator=1.2.1-2
fi
conf=/etc/systemd/zram-generator.conf.d
install -d "$conf"
prepare() {
    local device=$1 config=$2 alg=$3 priority=$4
    if [[ ! -e $conf/$config ]]; then
        if [[ -e /sys/block/$device/disksize && $(cat "/sys/block/$device/disksize") != 0 ]]; then
            echo "Stávající zařízení $device používá jiná konfigurace." >&2
            return 1
        fi
        printf '[%s]\nzram-size = 2048\ncompression-algorithm = %s\nswap-priority = %s\n' "$device" "$alg" "$priority" >"$conf/$config.tmp"
        mv -T "$conf/$config.tmp" "$conf/$config"
    fi
    if ! systemctl is-active --quiet "dev-$device.swap"; then
        systemctl daemon-reload
        systemctl start "dev-$device.swap"
    fi
    [[ $(cat "/sys/block/$device/disksize") == 2147483648 ]]
    awk -v name="/dev/$device" -v priority="$priority" '$1==name && $5==priority {found=1} END {exit !found}' /proc/swaps
}
prepare zram0 60-polarita-zulip.conf zstd 100
prepare zram1 62-polarita-stavba.conf lz4 80
# Při sestavení administrace dosáhla Medusa na hranici 192 MiB i s volnými zařízeními zram.
src=$(cd "$(dirname "$0")" && pwd)
budget=/etc/systemd/system/polarita-medusa-kompilace.service.d/50-zram.conf
if ! cmp -s "$src/../medusa/zram.conf" "$budget"; then
    install -D -m 0644 "$src/../medusa/zram.conf" "$budget"
    systemctl daemon-reload
fi
if awk 'NR>1 && $1 !~ /^\/dev\/zram[0-9]+$/ {other=1} END {exit other}' /proc/swaps; then
    printf '%s\n' 'vm.swappiness = 120' > /etc/sysctl.d/62-polarita-zram.conf
    sysctl -q -p /etc/sysctl.d/62-polarita-zram.conf
fi
bash "$(dirname "$0")/diskova-rezerva.sh"
echo 'Ve VM jsou aktivní dvě komprimovaná zařízení po 2 GiB.'
