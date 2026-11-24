#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
nft -c -f "$src/vstup.nft"
install -m0644 "$src/vstup.nft" /etc/polarita/silverbullet.nft
install -m0644 "$src/polarita-silverbullet-sit.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-silverbullet-sit.service
systemctl restart polarita-silverbullet-sit.service
bash "$src/../git/obnov-proxy.sh"
bash "$src/oidc.sh"
# Port Tailscale smí obsloužit pouze přihlášený web. Ostatní zóny zůstávají uzavřené.
bash "$src/../hrana/obnov-vstup.sh"
