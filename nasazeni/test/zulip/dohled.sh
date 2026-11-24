#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
host=${1:?Chybí název v síti VPN}
[[ $host =~ ^[a-z0-9.-]+\.ts\.net$ ]]
work=/srv/polarita/infra/checkmk-test/zulip
install -d -m 0755 /usr/local/lib/polarita-dohled
install -m 0644 "$src/dohled_odesli.py" /usr/local/lib/polarita-dohled/
python3 "$src/dohled_klic.py"
group=$(stat -c %g /srv/polarita/data/checkmk/test/polarita/var)
[[ $group =~ ^[1-9][0-9]*$ && $(incus exec -T checkmk-test -- id -g polarita) == "$group" ]]
# Oprávnění na idmapovaném svazku a přihlašovací údaje živého procesu mají různé mapování.
pid=$(incus query /1.0/instances/checkmk-test/state | python3 -c 'import json,sys;print(json.load(sys.stdin)["pid"])')
site_uid=$(incus exec -T checkmk-test -- id -u polarita)
sender_uid=$(awk -v uid="$site_uid" '$1 <= uid && uid < $1+$3 {print $2+uid-$1}' "/proc/$pid/uid_map")
[[ $sender_uid =~ ^[1-9][0-9]*$ ]]
install -d -m 0700 "$work"
cat >"$work/polarita-zulip-alert.socket" <<UNIT
[Unit]
Description=Doručení oznámení z instance Checkmk
RequiresMountsFor=/srv/polarita/data/checkmk/test
[Socket]
ListenStream=/srv/polarita/data/checkmk/test/.zulip-webhook.sock
SocketGroup=$group
SocketMode=0660
Accept=yes
RemoveOnStop=yes
[Install]
WantedBy=sockets.target
UNIT
cat >"$work/polarita-zulip-alert@.service" <<UNIT
[Unit]
Description=Doručení události Checkmk do testovacího chatu
[Service]
DynamicUser=yes
Environment=POLARITA_WEB=$host
Environment=POLARITA_NOTIFY_UID=$sender_uid
LoadCredentialEncrypted=zulip-webhook:/srv/polarita/data/bootstrap-test/openbao-test/zulip-webhook.cred
StandardInput=socket
StandardOutput=socket
StandardError=journal
ExecStart=/usr/bin/python3 /usr/local/lib/polarita-dohled/dohled_odesli.py
RuntimeMaxSec=25
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
RestrictAddressFamilies=AF_INET AF_UNIX
IPAddressDeny=any
IPAddressAllow=localhost
UNIT
install -m 0644 "$work"/polarita-zulip-alert{.socket,@.service} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-zulip-alert.socket
site=/omd/sites/polarita
incus file push --mode=0755 "$src/../dohled/notifikace.py" "checkmk-test$site/local/share/check_mk/notifications/polarita_zulip"
incus file push --mode=0644 "$src/polarita-zulip.mk" "checkmk-test$site/etc/check_mk/conf.d/"
incus exec -T checkmk-test -- runuser -l polarita -c 'cmk -O'
