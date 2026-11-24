#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T paperclip-test --)
"${inside[@]}" test -f /etc/polarita-paperclip/spravce-overen
"${inside[@]}" grep -qx PAPERCLIP_AUTH_DISABLE_SIGN_UP=true /etc/polarita-paperclip/server.env
nft -c -f "$src/vstup.nft"
install -m 0644 "$src/vstup.nft" /etc/polarita/paperclip.nft
install -m 0644 "$src/polarita-paperclip-sit.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-paperclip-sit.service
systemctl restart polarita-paperclip-sit.service
incus file push --mode=0644 "$src"/polarita-paperclip-vstup.{socket,service} paperclip-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-paperclip-vstup.socket
