#!/bin/bash
# Běží ve VM polarita-hq. TEST API používá soukromý socket v její stávající databázové instanci.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
files=(vykop.sql vykop.py vykop_api.py zkousky.sql osa.sql zkouska_knihy.sql kniha.py kniha.sql spisy.py spisy.sql sanony.sql spisy.html spisy.js model.py generator.py vzor.json formular.js zaznamy.py server.py mcp.py postgres.sh polarita-metadata.service zkouska.py)
rev=$(cd "$src" && sha256sum "${files[@]}" | sha256sum | cut -d' ' -f1)
target=/opt/polarita-metadata-test/releases/$rev
guest=(incus exec -T postgres-test --)
"${guest[@]}" install -d -m 0755 "$target"
tar --owner=0 --group=0 --mode=0644 -C "$src" -cf - "${files[@]}" | "${guest[@]}" tar -xpf - -C "$target"
"${guest[@]}" bash "$target/postgres.sh"
"${guest[@]}" python3 "$target/zkouska.py" "$target"
# Dva unixové konce spojují pouze databázový proces a portál přes namespace hostitelské VM.
relay=/srv/polarita/infra/metadata-test
install -d -m 0700 "$relay"
source "$src/../incus/unix-proxy.sh"
device postgres-test metadata-vystup bind=host listen="unix:$relay/api.sock" connect=unix:/run/polarita-metadata-test/api.sock mode=0600
device reditelstvi-test metadata-vstup bind=instance listen=unix:/run/polarita-metadata.sock connect="unix:$relay/api.sock" uid=65534 gid=65533 mode=0600
