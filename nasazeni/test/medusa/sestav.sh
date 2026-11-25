#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
app=/srv/polarita/apps/medusa-test
node=/srv/polarita/infra/medusa-test/distribuce/node-v26.13.1-linux-x64
cache=/srv/polarita/infra/medusa-test/npm-cache
role=pol-medusa-build
getent passwd "$role" >/dev/null || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin "$role"
install -dm0755 "$app/releases" /opt/polarita-medusa-node
install -dm0750 -o "$role" -g "$role" "$cache" /var/lib/polarita-medusa-build /var/cache/polarita-medusa-build
exec 9>/run/polarita-medusa-sestaveni.lock
flock 9
rev=$(cd "$src" && { sha256sum package.json package-lock.json tsconfig.json medusa-config.ts sestav.sh node.sh; find src -type f -print0 | sort -z | xargs -0 sha256sum; } | sha256sum | cut -d' ' -f1)
release=$app/releases/$rev
if [[ ! -d $release ]]; then
    tmp=$(mktemp -d "$app/releases/.sestaveni-XXXXXXXX")
    trap 'rm -rf -- "$tmp"' EXIT
    cp -r "$src/src" "$src"/{package.json,package-lock.json,tsconfig.json,medusa-config.ts} "$tmp/"
    chmod -R a+rX "$tmp/src"
    chmod 0644 "$tmp"/{package.json,package-lock.json,tsconfig.json,medusa-config.ts}
    chown "$role:$role" "$tmp"
    run=(systemd-run --quiet --pipe --wait --collect --service-type=exec
        -p User="$role" -p Group="$role" -p PrivateTmp=yes -p PrivateDevices=yes -p ProtectSystem=strict
        -p NoNewPrivileges=yes -p ProtectHome=yes -p InaccessiblePaths=/srv -p UMask=0022
        -p "BindPaths=$tmp:/var/lib/polarita-medusa-build" -p "BindPaths=$cache:/var/cache/polarita-medusa-build"
        -p "BindReadOnlyPaths=$node:/opt/polarita-medusa-node" -p 'ReadWritePaths=/var/lib/polarita-medusa-build /var/cache/polarita-medusa-build'
        -p WorkingDirectory=/var/lib/polarita-medusa-build -p MemoryHigh=750M -p MemoryMax=1200M -p CPUQuota=70% -p Nice=10 -p IOWeight=10 -p IOSchedulingClass=idle
        -E PATH=/opt/polarita-medusa-node/bin:/usr/bin:/bin -E HOME=/var/lib/polarita-medusa-build
        -E npm_config_cache=/var/cache/polarita-medusa-build -E MEDUSA_DISABLE_TELEMETRY=true
        -E POLARITA_MEDUSA_BUILD=1 -E NODE_OPTIONS=--max-old-space-size=768)
    exec 8>/run/polarita-test-zatez.lock
    flock 8
    "${run[@]}" /usr/bin/env npm ci --ignore-scripts --prefer-offline --no-audit --no-fund --registry=https://registry.npmjs.org/
    "${run[@]}" -p PrivateNetwork=yes -E POLARITA_MEDUSA_BACKEND=1 /usr/bin/env npm run build
    "${run[@]}" -p PrivateNetwork=yes /usr/bin/env npm run build -- --admin-only
    [[ -s $tmp/.medusa/server/medusa-config.js && -s $tmp/.medusa/admin/index.html ]]
    install -d "$tmp/.medusa/server/public"
    mv -T "$tmp/.medusa/admin" "$tmp/.medusa/server/public/admin"
    chmod 0755 "$tmp"
    mv -T "$tmp" "$release"
    trap - EXIT
fi
ln -sfn "releases/$rev" "$app/.candidate-next"
mv -Tf "$app/.candidate-next" "$app/candidate"
printf 'Medusa 2.23.0, aplikační API a správní rozhraní jsou sestaveny.\n'
