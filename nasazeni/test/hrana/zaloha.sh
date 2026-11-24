#!/bin/bash
# Lokální konzistentní export Headscale včetně WAL, identity serveru a konfigurace.
set -euo pipefail
umask 077
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
base=/srv/polarita/backups/headscale
install -d -m 0700 "$base"
exec 9>"$base/.lock"
flock -x 9
tmp=$(mktemp -d "$base/.export-XXXXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
cd "$tmp"
incus storage volume export default headscale-test-data volume.tar --volume-only --compression none >/dev/null
mkdir overeni
tar -xf volume.tar -C overeni backup/volume
python3 - <<'PY'
from pathlib import Path
import sqlite3
root = Path("overeni/backup/volume")
for key in ("noise.key", "derp.key"):
    if (root/key).stat().st_size == 0:
        raise SystemExit("Prázdný strojový klíč obnovy")
with sqlite3.connect(root / "db.sqlite") as conn:
    if conn.execute("pragma integrity_check").fetchall() != [("ok",)]:
        raise SystemExit("Chyba integrity SQLite")
    for table in ("users", "nodes", "pre_auth_keys"):
        conn.execute(f"select count(*) from {table}").fetchone()
PY
cp -a /srv/polarita/infra/hrana/headscale konfigurace
tar -cf zaloha.tar volume.tar konfigurace
mv zaloha.tar "$base/posledni.tar"
echo 'Export Headscale ověřen obnovením databáze a kontrolou integrity SQLite.'
