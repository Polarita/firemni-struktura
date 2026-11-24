#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
root=/srv/polarita/data/legal-archive
dataset=polarita_zfs/data/legal-archive/test
[[ $(findmnt -n -o SOURCE --mountpoint "$root") == polarita_zfs/data/legal-archive ]]
if ! zfs list -Ho name "$dataset" >/dev/null 2>&1; then
    [[ ! -e "$root/test" ]]
    zfs create -o mountpoint="$root/test" -o compression=lz4 -o exec=off -o devices=off -o setuid=off "$dataset"
fi
if [[ $(zfs get -Ho value mounted "$dataset") != yes ]]; then zfs mount "$dataset"; fi
[[ $(findmnt -n -o SOURCE --mountpoint "$root/test") == "$dataset" ]]
[[ $(zfs get -Ho value encryptionroot "$dataset") == polarita_zfs ]]
id polarita-archiv-test >/dev/null 2>&1 || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin polarita-archiv-test
for p in /srv/polarita /srv/polarita/data "$root"; do setfacl -m u:polarita-archiv-test:--x "$p"; done
chown root:polarita-archiv-test "$root/test"
chmod 0750 "$root/test"
install -d -m 0700 "$root/test/.priprava"
install -D -m 0755 "$src/pripoj.sh" /usr/local/lib/polarita/pripoj-archiv-test
install -m 0644 "$src/polarita-archiv-test.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-archiv-test.service
python3 "$src/zkouska.py"
