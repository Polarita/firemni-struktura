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
git_inside=(incus exec -T gitea-test --)
# OIDC používá existující TLS vstup a pouze povolené cesty realmu.
if ! "${git_inside[@]}" cmp -s /etc/polarita-gitea/Caddyfile - <"$src/../git/Caddyfile"; then
    incus file push --mode=0644 "$src/../git/Caddyfile" gitea-test/etc/polarita-gitea/Caddyfile.next
    "${git_inside[@]}" bash -ec 'set -a; . /etc/polarita-gitea/vstup.env; /opt/gitea/caddy validate --config /etc/polarita-gitea/Caddyfile.next --adapter caddyfile; mv -T /etc/polarita-gitea/Caddyfile.next /etc/polarita-gitea/Caddyfile; systemctl restart gitea-vstup'
fi
bash "$src/oidc.sh"
# Port Tailscale smí obsloužit pouze přihlášený web. Ostatní zóny zůstávají uzavřené.
nft -c -f "$src/../zones.nft"
install -m0644 "$src/../zones.nft" /etc/polarita/zones.nft
nft -f /etc/polarita/zones.nft
conf=/srv/polarita/infra/hrana/conf
install -m0644 "$src/../hrana/Caddyfile" "$conf/Caddyfile.silverbullet-next"
edge=(incus exec -T caddy-test --)
"${edge[@]}" caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile.silverbullet-next
mv -T "$conf/Caddyfile.silverbullet-next" "$conf/Caddyfile"
"${edge[@]}" caddy reload --adapter caddyfile --config /etc/caddy/Caddyfile
