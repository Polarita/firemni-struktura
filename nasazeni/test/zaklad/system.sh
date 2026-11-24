#!/bin/bash
set -euo pipefail
umask 077
owner=$1
[[ $owner =~ ^[0-9a-f-]{36}$ && $EUID == 0 && $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
[[ -c /dev/tpmrm0 && -c /dev/kvm && -d /sys/firmware/efi ]]
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 26.04 ]]
install -d -m 0700 /etc/polarita
if [[ -e /etc/polarita/zalozeni-vm ]]; then
    [[ $(cat /etc/polarita/zalozeni-vm) == "$owner" ]]
else
    [[ ! -e /etc/polarita/zfs && ! -e /etc/systemd/system/polarita-zfs.service ]]
    printf '%s\n' "$owner" > /etc/polarita/zalozeni-vm.next
    mv -T /etc/polarita/zalozeni-vm.next /etc/polarita/zalozeni-vm
fi
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=300 update
apt-get -o DPkg::Lock::Timeout=300 -y install zfsutils-linux chrony auditd unattended-upgrades openssh-server openssl ca-certificates
modprobe zfs
systemd-analyze has-tpm2 --quiet
[[ $(od -An -tu1 -j4 -N1 /sys/firmware/efi/efivars/SecureBoot-* | tr -d ' ') == 1 ]]
timedatectl set-timezone Europe/Prague
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'CFG'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CFG
cat >/etc/apt/apt.conf.d/52polarita-security <<'CFG'
#clear Unattended-Upgrade::Allowed-Origins;
Unattended-Upgrade::Allowed-Origins { "${distro_id}:${distro_codename}-security"; };
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
CFG
install -d -m 0755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/00-polarita.conf <<'CFG'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
CFG
sshd -t
systemctl enable --now chrony.service auditd.service apt-daily-upgrade.timer
systemctl reload-or-restart ssh.service
