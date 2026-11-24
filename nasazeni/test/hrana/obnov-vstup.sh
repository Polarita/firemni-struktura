#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-obnov-vstup.lock
flock 8
nft -c -f "$src/../zones.nft"
install -m0644 "$src/../zones.nft" /etc/polarita/zones.nft
nft -f /etc/polarita/zones.nft
conf=/srv/polarita/infra/hrana/conf
install -m0644 "$src/Caddyfile" "$conf/Caddyfile.vstup-next"
edge=(incus exec -T caddy-test --)
"${edge[@]}" caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile.vstup-next
mv -T "$conf/Caddyfile.vstup-next" "$conf/Caddyfile"
"${edge[@]}" caddy reload --adapter caddyfile --config /etc/caddy/Caddyfile
