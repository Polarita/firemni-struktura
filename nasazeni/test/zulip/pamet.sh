#!/bin/bash
# Komprimovaná odkládací paměť pro testovací server s 5 GiB RAM.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
if (( $(awk '/MemTotal:/ {print $2}' /proc/meminfo) >= 5*1024*1024 )); then exit 0; fi
if (( $(awk '/SwapTotal:/ {print $2}' /proc/meminfo) >= 2000000 )); then exit 0; fi
DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 -y --no-install-recommends install systemd-zram-generator=1.2.1-2
install -d /etc/systemd/zram-generator.conf.d
cat >/etc/systemd/zram-generator.conf.d/60-polarita-zulip.conf <<'CONF'
[zram0]
zram-size = 2048
compression-algorithm = zstd
swap-priority = 100
CONF
systemctl daemon-reload
systemctl start dev-zram0.swap
[[ $(cat /sys/block/zram0/disksize) == 2147483648 ]]
grep -q '^/dev/zram0 ' /proc/swaps
echo 'Ředitelství má 2 GiB komprimované odkládací paměti v RAM.'
