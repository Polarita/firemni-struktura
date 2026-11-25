#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
state=/srv/polarita/workspace/ecomail-test
key=/etc/polarita-ecomail-test
role=pol-ecomail-test
[[ $(findmnt -no SOURCE -T /srv/polarita/workspace) == polarita_zfs/workspace ]]
[[ $(zfs get -H -o value encryption polarita_zfs/workspace) == aes-256-gcm ]]
exec 9>/run/polarita-ecomail-instalace.lock
flock 9
if ! /usr/bin/python3 -I -c 'import dkim' 2>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=180 install -y --no-install-recommends python3-dkim
fi
id "$role" >/dev/null 2>&1 || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin "$role"
install -dm0700 -o "$role" -g "$role" "$state"
install -dm0750 -o root -g "$role" "$key"
if [[ ! -s $key/test.key ]]; then
    (umask 077; openssl genpkey -quiet -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$key/.next")
    chgrp "$role" "$key/.next"
    chmod 0640 "$key/.next"
    mv -T "$key/.next" "$key/test.key"
fi
openssl pkey -in "$key/test.key" -pubout -outform DER -out "$key/test.der"
chmod 0644 "$key/test.der"
install -Dm0644 "$src/retence.py" /opt/polarita-ecomail-test/retence.py
install -dm0755 /var/lib/polarita-ecomail-data
install -Dm0755 "$src/prikaz.sh" /usr/local/sbin/polarita-ecomail-test
/usr/local/sbin/polarita-ecomail-test init
install -m0644 "$src"/polarita-ecomail{.socket,@.service} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-ecomail.socket
source "$src/../incus/unix-proxy.sh"
device reditelstvi-test ecomail-odhlaseni bind=instance listen=unix:/run/polarita-ecomail.sock connect=unix:/run/polarita-ecomail-test/odhlaseni.sock uid=65534 gid=65533 mode=0600
