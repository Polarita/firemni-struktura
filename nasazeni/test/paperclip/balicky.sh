#!/bin/bash
# Sestaví reprodukovatelný strom serveru a jeho webového rozhraní bez provozních přístupů.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
cache=/srv/polarita/infra/paperclip-test
node=$cache/distribuce/node-v24.22.3-linux-x64
publish=/var/lib/polarita-paperclip-distribuce
lockfile=$src/package-lock.json
hash=$(sha256sum "$lockfile" | cut -d' ' -f1)
install -d -m 0755 "$publish"
exec 9>"$cache/.balicky"
flock 9
if [[ ! -d $publish/$hash ]]; then
    python3 -c '
import json,sys
p=json.load(sys.stdin)["packages"]["node_modules/@paperclipai/server"]
if p["version"]!="2026.1117.0" or p["integrity"]!="sha512-Aw5uIQjP0E78k1oCPI5B6706MYh20xMkg0nq8i9rMXD8eqbH1gzl2JBQynM/3jL91zx0rr1Csz0TUaLhcnpBjA==":
    sys.exit("Uzamčené vydání Paperclipu nesouhlasí")' <"$lockfile"
    systemd-run --quiet --wait --collect \
        -p DynamicUser=yes -p CacheDirectory=polarita-paperclip-sestaveni -p PrivateTmp=yes \
        -p PrivateDevices=yes -p ProtectSystem=strict -p ProtectHome=yes -p NoNewPrivileges=yes \
        -p "BindReadOnlyPaths=$node:/opt/node $src/package.json:/opt/paperclip-package.json $lockfile:/opt/paperclip-lock.json" \
        -p MemoryMax=1550M -p CPUQuota=120% -p Nice=10 \
        -E PATH=/opt/node/bin:/usr/bin:/bin -E HOME=/var/cache/polarita-paperclip-sestaveni \
        -E npm_config_cache=/var/cache/polarita-paperclip-sestaveni/npm -E NODE_OPTIONS=--max-old-space-size=600 \
        -E TMPDIR=/var/cache/polarita-paperclip-sestaveni/tmp -E "POLARITA_PACKAGE_HASH=$hash" \
        -p WorkingDirectory=/var/cache/polarita-paperclip-sestaveni /bin/bash -ec '
            mkdir -p tmp "server-$POLARITA_PACKAGE_HASH"
            cd "server-$POLARITA_PACKAGE_HASH"
            cp /opt/paperclip-package.json package.json
            cp /opt/paperclip-lock.json package-lock.json
            npm ci --omit=dev --ignore-scripts --no-audit --no-fund --maxsockets=3 --registry=https://registry.npmjs.org
            test -s node_modules/@paperclipai/server/ui-dist/index.html
            node --check node_modules/@paperclipai/server/dist/index.js
            node --input-type=module -e "await import(\"postgres\"); await import(\"@paperclipai/db\");"
        '
    tree="/var/cache/polarita-paperclip-sestaveni/server-$hash"
    [[ $(stat -c %d "$tree") == "$(stat -c %d "$publish")" ]]
    chown -hR root:root "$tree"
    chmod -R go-w "$tree"
    mv -T "$tree" "$publish/$hash"
fi
[[ -s $publish/$hash/node_modules/@paperclipai/server/ui-dist/index.html ]]
ln -sfn "$hash" "$publish/.nova"
mv -Tf "$publish/.nova" "$publish/current"
echo 'Oficiální webové rozhraní, server a závislosti Paperclipu jsou připravené v ředitelství.'
