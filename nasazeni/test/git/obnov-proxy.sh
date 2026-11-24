#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-obnov-git-proxy.lock
flock 8
git_inside=(incus exec -T gitea-test --)
# OIDC používá existující TLS vstup a pouze povolené cesty realmu.
if ! "${git_inside[@]}" cmp -s /etc/polarita-gitea/Caddyfile - <"$src/Caddyfile"; then
    incus file push --mode=0644 "$src/Caddyfile" gitea-test/etc/polarita-gitea/Caddyfile.next
    "${git_inside[@]}" bash -ec 'set -a; . /etc/polarita-gitea/vstup.env; /opt/gitea/caddy validate --config /etc/polarita-gitea/Caddyfile.next --adapter caddyfile; mv -T /etc/polarita-gitea/Caddyfile.next /etc/polarita-gitea/Caddyfile; systemctl restart gitea-vstup'
fi
