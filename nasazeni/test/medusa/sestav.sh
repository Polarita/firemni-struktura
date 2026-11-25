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
    state=$app/.sestaveni/$rev
    tmp=$state/prace
    install -dm0700 "$app/.sestaveni" "$state"
    if [[ ! -d $tmp ]]; then
        source_copy=$(mktemp -d "$state/.podklad-XXXXXXXX")
        cp -r "$src/src" "$src"/{package.json,package-lock.json,tsconfig.json,medusa-config.ts} "$source_copy/"
        chmod -R a+rX "$source_copy/src"
        chmod 0644 "$source_copy"/{package.json,package-lock.json,tsconfig.json,medusa-config.ts}
        chown "$role:$role" "$source_copy"
        mv -T "$source_copy" "$tmp"
    fi
    run=(systemd-run --unit=polarita-medusa-kompilace --quiet --pipe --wait --collect --service-type=exec
        -p User="$role" -p Group="$role" -p PrivateTmp=yes -p PrivateDevices=yes -p ProtectSystem=strict
        -p NoNewPrivileges=yes -p ProtectHome=yes -p InaccessiblePaths=/srv -p UMask=0022
        -p "BindPaths=$tmp:/var/lib/polarita-medusa-build" -p "BindPaths=$cache:/var/cache/polarita-medusa-build"
        -p "BindReadOnlyPaths=$node:/opt/polarita-medusa-node" -p 'ReadWritePaths=/var/lib/polarita-medusa-build /var/cache/polarita-medusa-build'
        -p WorkingDirectory=/var/lib/polarita-medusa-build -p MemoryMax=1200M -p MemorySwapMax=192M -p CPUQuota=70% -p Nice=10 -p IOWeight=10 -p IOSchedulingClass=idle
        -E PATH=/opt/polarita-medusa-node/bin:/usr/bin:/bin -E HOME=/var/lib/polarita-medusa-build
        -E npm_config_cache=/var/cache/polarita-medusa-build -E MEDUSA_DISABLE_TELEMETRY=true
        -E POLARITA_MEDUSA_BUILD=1 -E NODE_OPTIONS=--max-old-space-size=768)
    exec 8>/run/polarita-test-zatez.lock
    flock 8
    # Soubor s dokončenou fází zůstává mimo adresář dostupný sestavovacímu účtu.
    phase=
    if [[ -f $state/dokonceno ]]; then read -r phase <"$state/dokonceno"; fi
    dokonci() {
        sync -f "$tmp"
        printf '%s\n' "$1" >"$state/.dokonceno-next"
        mv -T "$state/.dokonceno-next" "$state/dokonceno"
        phase=$1
        printf 'Medusa TEST – dokončena fáze %s.\n' "$phase"
    }
    case $phase in ''|zavislosti|server|admin) ;; *) echo 'Neznámý stav sestavení Medusy.' >&2; exit 1 ;; esac
    if [[ -z $phase ]]; then
        "${run[@]}" -p MemoryHigh=750M /usr/bin/env npm ci --ignore-scripts --prefer-offline --no-audit --no-fund --registry=https://registry.npmjs.org/
        [[ -x $tmp/node_modules/.bin/medusa ]]
        dokonci zavislosti
    fi
    if [[ $phase == zavislosti ]]; then
        "${run[@]}" -p MemoryHigh=750M -p PrivateNetwork=yes -E POLARITA_MEDUSA_BACKEND=1 /usr/bin/env npm run build
        [[ -s $tmp/.medusa/server/medusa-config.js ]]
        dokonci server
    fi
    if [[ $phase == server ]]; then
        "${run[@]}" -p MemoryHigh=896M -p PrivateNetwork=yes /usr/bin/env npm run build -- --admin-only
        [[ -s $tmp/.medusa/admin/index.html ]]
        dokonci admin
    fi
    if [[ -d $tmp/.medusa/admin ]]; then
        install -d "$tmp/.medusa/server/public"
        mv -T "$tmp/.medusa/admin" "$tmp/.medusa/server/public/admin"
    fi
    [[ -x $tmp/node_modules/.bin/medusa && -s $tmp/.medusa/server/medusa-config.js && -s $tmp/.medusa/server/public/admin/index.html ]]
    chmod 0755 "$tmp"
    mv -T "$tmp" "$release"
fi
ln -sfn "releases/$rev" "$app/.candidate-next"
mv -Tf "$app/.candidate-next" "$app/candidate"
printf 'Medusa 2.23.0, aplikační API a správní rozhraní jsou sestaveny.\n'
