#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == karantena-test && $(ls /sys/class/net) == lo ]]
id karantena >/dev/null 2>&1 || useradd --uid 17304 --user-group --create-home --shell /bin/bash karantena
[[ $(id -u karantena) == 17304 && $(id -g karantena) == 17304 ]]
# Podman bez roota používá uživatelský namespace a vlastní podřízené rozsahy UID/GID.
grep -q '^karantena:' /etc/subuid
grep -q '^karantena:' /etc/subgid
install -d -m 0755 /opt/polarita
cat > /etc/tmpfiles.d/polarita-karantena.conf <<'CONF'
d /run/user/17304 0700 karantena karantena -
CONF
systemd-tmpfiles --create /etc/tmpfiles.d/polarita-karantena.conf
loginctl enable-linger karantena
systemctl start user@17304.service
cat >/opt/polarita/pamet.sh <<'MEM'
#!/bin/bash
set -euo pipefail
modprobe zram
if ! grep -q '^/dev/zram0 ' /proc/swaps; then
    if [[ $(cat /sys/block/zram0/disksize) == 0 ]]; then
        echo 1610612736 > /sys/block/zram0/disksize
        mkswap /dev/zram0 >/dev/null
    fi
    swapon -p 100 /dev/zram0
fi
MEM
chmod 0755 /opt/polarita/pamet.sh
cat > /etc/systemd/system/polarita-karantena-pamet.service <<'UNIT'
[Unit]
Description=Komprimovaná pracovní paměť pro offline konverzi
After=systemd-modules-load.service
[Service]
Type=oneshot
ExecStart=/opt/polarita/pamet.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now polarita-karantena-pamet.service
for mount in /mnt/karantena-in /mnt/karantena-out /mnt/clamav-db; do mountpoint -q "$mount"; done
dpkg-query -W -f='${Version}\n' dangerzone-full
cd /home/karantena
runuser -u karantena -- env XDG_RUNTIME_DIR=/run/user/17304 podman info --format '{{.Host.Security.Rootless}}' | grep -Fx true
