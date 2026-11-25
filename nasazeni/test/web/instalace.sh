#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
apps=/srv/polarita/apps/web-polarita-cz
node=/srv/polarita/infra/paperclip-test/distribuce/node-v24.22.3-linux-x64
[[ $("$node/bin/node" --version) == v24.22.3 ]]
install -d -m 0755 "$apps/releases" "$apps/podklady"
exec 9>"$apps/.instalace"
flock 9
tmp=$(mktemp -d "$apps/.priprava-XXXXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
install -m0644 "$src"/{package.json,package-lock.json,astro.config.mjs,tsconfig.json,sestav.sh} "$tmp/"
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
    source_dir="$apps/podklady/$rev"
    if [[ ! -d $source_dir ]]; then
        cp -r "$tmp" "$tmp-podklad"
        mv -T "$tmp-podklad" "$source_dir"
    fi
    build=(systemd-run --quiet --no-block -p Type=exec -p RemainAfterExit=yes -p DynamicUser=yes -p User=polarita-web-build
        -p CacheDirectory=polarita-web-build -p "WorkingDirectory=$cache" -p PrivateTmp=yes -p PrivateDevices=yes
        -p ProtectSystem=strict -p ProtectHome=yes -p NoNewPrivileges=yes -p Nice=12 -p CPUQuota=90%
        -p MemoryMax=750M -p "BindReadOnlyPaths=$node:/opt/node $source_dir:/opt/polarita-web-src"
        -E PATH=/opt/node/bin:/usr/bin:/bin -E "HOME=$cache" -E ASTRO_TELEMETRY_DISABLED=1
        -E NODE_OPTIONS=--max-old-space-size=450)
    for phase in zavislosti sestaveni; do
        unit="polarita-web-$phase-$rev.service"
        stamp="$cache/$rev/.$phase.ok"
        if [[ -f $stamp && $(cat "$stamp") == "$rev" ]]; then continue; fi
        if systemctl is-failed --quiet "$unit"; then systemctl reset-failed "$unit"; fi
        if [[ $(systemctl show -p LoadState --value "$unit") == not-found ]]; then
            phase_options=()
            if [[ $phase == sestaveni ]]; then
                # CacheDirectory dynamického účtu má noexec. CLI a nativní moduly potřebuje až offline sestavení.
                phase_options=(-p PrivateNetwork=yes -p "ExecPaths=$(realpath "$cache")/$rev/node_modules")
            fi
            "${build[@]}" --unit="$unit" "${phase_options[@]}" /bin/bash /opt/polarita-web-src/sestav.sh "$phase" "$rev" ||
                systemctl cat "$unit" >/dev/null
        fi
        while true; do
            if [[ -f $stamp && $(cat "$stamp") == "$rev" ]]; then break; fi
            if sub=$(systemctl show -p SubState --value "$unit"); then
                case "$sub" in
                    failed|dead|exited)
                        if [[ -f $stamp && $(cat "$stamp") == "$rev" ]]; then break; fi
                        journalctl -u "$unit" -n 15 --no-pager
                        exit 1 ;;
                esac
            fi
            sleep 3
        done
        systemctl stop "$unit"
    done
    out="$cache/$rev/dist"
    python3 "$src/over.py" "$out" "$tmp/src/cenik-verejny.json"
    install -d "$tmp/dist/prevzeti-sanonu" "$tmp/dist/kalkulacka-svj"
    install -m0644 "$out/kalkulacka-svj/index.html" "$tmp/dist/kalkulacka-svj/"
    install -m0644 "$out/index.html" "$out/llms.txt" "$tmp/dist/"
    install -m0644 "$out/prevzeti-sanonu/index.html" "$tmp/dist/prevzeti-sanonu/"
    mv -T "$tmp" "$release"
    flock -u 8
fi
python3 "$src/over.py" "$release/dist" "$release/src/cenik-verejny.json"
vm=reditelstvi-test
[[ $(incus config get "$vm" user.polarita.role) == "$vm" ]]
bash "$src/typst.sh"
web=/usr/local/share/polarita-web
inside=(incus exec -T "$vm" --)
"${inside[@]}" mkdir -p "$web"
if ! "${inside[@]}" test -d "$web/$rev"; then
    "${inside[@]}" mkdir -p "$web/.$rev-next"
    tar -cf - -C "$release/dist" . | "${inside[@]}" tar xf - -C "$web/.$rev-next"
    (cd "$release/dist" && sha256sum index.html llms.txt prevzeti-sanonu/index.html kalkulacka-svj/index.html) |
        "${inside[@]}" sh -ec 'cd "$1"; sha256sum -c -' web "$web/.$rev-next"
    "${inside[@]}" mv -T "$web/.$rev-next" "$web/$rev"
fi
(cd "$release/dist" && sha256sum index.html llms.txt prevzeti-sanonu/index.html kalkulacka-svj/index.html) |
    "${inside[@]}" sh -ec 'cd "$1"; sha256sum -c -' web "$web/$rev"
"${inside[@]}" sh -ec 'cd "$1"; ln -sfn "$2" .current-next; mv -Tf .current-next current' web "$web" "$rev"
ln -sfn "releases/$rev" "$apps/.current-next"
mv -Tf "$apps/.current-next" "$apps/current"
