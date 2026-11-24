#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
apps=/srv/polarita/apps/web-polarita-cz
node=/srv/polarita/infra/paperclip-test/distribuce/node-v24.22.3-linux-x64
[[ $("$node/bin/node" --version) == v24.22.3 ]]
install -d -m 0755 "$apps/releases"
exec 9>"$apps/.instalace"
flock 9
tmp=$(mktemp -d "$apps/.priprava-XXXXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
install -m0644 "$src"/{package.json,package-lock.json,astro.config.mjs,tsconfig.json} "$tmp/"
cp -r "$src/src" "$tmp/src"
python3 -B - "$src/../../../balicky/S3-konfigurator-a-tarify" > "$tmp/src/cenik-verejny.json" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from pricing import load_price_list, public_price_list
data=public_price_list(load_price_list())
if not data["meta"]["approved"]:
    raise ValueError("Chybí schválená verze zdroje cen.")
print(json.dumps(data,ensure_ascii=False))
PY
find "$tmp" -type d -exec chmod 0755 {} +
find "$tmp" -type f -exec chmod 0644 {} +
rev=$(cd "$tmp" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
release="$apps/releases/$rev"
if [[ ! -d $release ]]; then
    exec 8>/run/polarita-test-zatez.lock
    flock 8
    cache=/var/cache/polarita-web-build
    build=(systemd-run --quiet --wait --pipe --collect -p DynamicUser=yes -p User=polarita-web-build
        -p CacheDirectory=polarita-web-build -p "WorkingDirectory=$cache" -p PrivateTmp=yes -p PrivateDevices=yes
        -p ProtectSystem=strict -p ProtectHome=yes -p NoNewPrivileges=yes -p Nice=12 -p CPUQuota=90%
        -p MemoryMax=750M -p "BindReadOnlyPaths=$node:/opt/node $tmp:/opt/polarita-web-src"
        -E PATH=/opt/node/bin:/usr/bin:/bin -E "HOME=$cache" -E ASTRO_TELEMETRY_DISABLED=1
        -E NODE_OPTIONS=--max-old-space-size=450)
    "${build[@]}" /bin/bash -ec '
        mkdir -p projekt
        cp /opt/polarita-web-src/package*.json projekt/
        cd projekt
        npm ci --ignore-scripts --no-audit --no-fund --maxsockets=3 --registry=https://registry.npmjs.org'
    "${build[@]}" -p PrivateNetwork=yes /bin/bash -ec '
        cd projekt
        rm -rf src dist .astro
        cp -r /opt/polarita-web-src/src .
        cp /opt/polarita-web-src/{astro.config.mjs,tsconfig.json} .
        npm run build'
    out="$cache/projekt/dist"
    python3 "$src/over.py" "$out" "$tmp/src/cenik-verejny.json"
    install -d "$tmp/dist/prevzeti-sanonu"
    install -m0644 "$out/index.html" "$out/llms.txt" "$tmp/dist/"
    install -m0644 "$out/prevzeti-sanonu/index.html" "$tmp/dist/prevzeti-sanonu/"
    mv -T "$tmp" "$release"
    flock -u 8
fi
python3 "$src/over.py" "$release/dist" "$release/src/cenik-verejny.json"
vm=reditelstvi-test
[[ $(incus config get "$vm" user.polarita.role) == "$vm" ]]
web=/usr/local/share/polarita-web
inside=(incus exec -T "$vm" --)
"${inside[@]}" mkdir -p "$web"
if ! "${inside[@]}" test -d "$web/$rev"; then
    "${inside[@]}" mkdir -p "$web/.$rev-next"
    tar -cf - -C "$release/dist" . | "${inside[@]}" tar xf - -C "$web/.$rev-next"
    (cd "$release/dist" && sha256sum index.html llms.txt prevzeti-sanonu/index.html) |
        "${inside[@]}" sh -ec 'cd "$1"; sha256sum -c -' web "$web/.$rev-next"
    "${inside[@]}" mv -T "$web/.$rev-next" "$web/$rev"
fi
(cd "$release/dist" && sha256sum index.html llms.txt prevzeti-sanonu/index.html) |
    "${inside[@]}" sh -ec 'cd "$1"; sha256sum -c -' web "$web/$rev"
"${inside[@]}" sh -ec 'cd "$1"; ln -sfn "$2" .current-next; mv -Tf .current-next current' web "$web" "$rev"
ln -sfn "releases/$rev" "$apps/.current-next"
mv -Tf "$apps/.current-next" "$apps/current"
