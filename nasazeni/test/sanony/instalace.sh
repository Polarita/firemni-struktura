#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
queue=/srv/polarita/workspace/karantena
relay=/srv/polarita/infra/metadata-test
db=(incus exec -T postgres-test --)
[[ $(findmnt -no SOURCE -T "$queue") == polarita_zfs/* ]]
install -dm0700 "$queue/sanony" "$queue/vstup" "$relay"
install -Dm0644 "$src/prijem.py" /srv/polarita/infra/karantena-test/bin/sanony/prijem.py
install -m0644 "$src/archiv.py" /srv/polarita/infra/karantena-test/bin/sanony/archiv.py
install -m0644 "$src/../paperless/over_dokument.py" /srv/polarita/infra/paperless-test/conf/.prijmi_dokument.next
mv -T /srv/polarita/infra/paperless-test/conf/.prijmi_dokument.next /srv/polarita/infra/paperless-test/conf/prijmi_dokument.py
"${db[@]}" install -dm0755 /opt/polarita-sanony
incus file push --mode=0644 "$src/registr.py" postgres-test/opt/polarita-sanony/registr.py
for file in "$src"/polarita-sanony-registr*; do
    incus file push --mode=0644 "$file" "postgres-test/etc/systemd/system/$(basename "$file")"
done
"${db[@]}" systemctl daemon-reload
"${db[@]}" systemctl enable --now polarita-sanony-registr.socket
install -m0644 "$src"/polarita-sanony{.socket,@.service,-obnova.service,-obnova.timer,-archiv.service,-archiv.timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-sanony.socket polarita-sanony-obnova.timer polarita-sanony-archiv.timer
source "$src/../incus/unix-proxy.sh"
device postgres-test sanony-registr bind=host listen="unix:$relay/sanony.sock" connect=unix:/run/polarita-sanony-registr.sock mode=0600
device reditelstvi-test sanony-prijem bind=instance listen=unix:/run/polarita-sanony.sock connect="unix:$relay/prijem.sock" uid=65534 gid=65533 mode=0600
