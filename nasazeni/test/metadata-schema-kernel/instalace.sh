#!/bin/bash
# Běží ve VM polarita-hq. TEST API používá soukromý socket v její stávající databázové instanci.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
files=(model.py generator.py vzor.json formular.js zaznamy.py server.py mcp.py postgres.sh polarita-metadata.service zkouska.py)
rev=$(cd "$src" && sha256sum "${files[@]}" | sha256sum | cut -d' ' -f1)
target=/opt/polarita-metadata-test/releases/$rev
guest=(incus exec -T postgres-test --)
"${guest[@]}" install -d -m 0755 "$target"
tar -C "$src" -cf - "${files[@]}" | "${guest[@]}" tar -xf - -C "$target"
"${guest[@]}" bash "$target/postgres.sh"
"${guest[@]}" python3 "$target/zkouska.py" "$target"
# Dva unixové konce spojují pouze databázový proces a portál přes namespace hostitelské VM.
relay=/srv/polarita/infra/metadata-test
install -d -m 0700 "$relay"
device() {
    local instance=$1 name=$2 pair key
    shift 2
    [[ $(incus config get "$instance" user.polarita.role) == "$instance" ]]
    if ! incus config device list "$instance" | grep -Fxq "$name"; then
        incus config device add "$instance" "$name" proxy "$@"
    fi
    for pair in "$@"; do
        key=${pair%%=*}
        [[ $(incus config device get "$instance" "$name" "$key") == "${pair#*=}" ]]
    done
}
device postgres-test metadata-vystup bind=host listen="unix:$relay/api.sock" connect=unix:/run/polarita-metadata-test/api.sock mode=0600
device reditelstvi-test metadata-vstup bind=instance listen=unix:/run/polarita-metadata.sock connect="unix:$relay/api.sock" uid=65534 gid=65533 mode=0600
