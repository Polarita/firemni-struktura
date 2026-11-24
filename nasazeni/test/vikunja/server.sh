#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
host=${1:?Chybí název TEST}
[[ $host =~ ^[a-z0-9.-]+\.ts\.net$ ]]
inside=(incus exec -T vikunja-test --)
nft -c -f "$src/vstup.nft"
install -m0644 "$src/vstup.nft" /etc/polarita/vikunja.nft
install -m0644 "$src/polarita-vikunja-sit.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-vikunja-sit.service
systemctl restart polarita-vikunja-sit.service
"${inside[@]}" bash -ec '
    getent group pol-vikunja >/dev/null || groupadd --gid 17320 pol-vikunja
    id pol-vikunja >/dev/null 2>&1 || useradd --uid 17320 --gid 17320 --no-create-home --home-dir /var/lib/vikunja --shell /usr/sbin/nologin pol-vikunja
    [[ $(id -u pol-vikunja) == 17320 && $(id -g pol-vikunja) == 17320 ]]
    mountpoint -q /var/lib/vikunja
    chown pol-vikunja:pol-vikunja /var/lib/vikunja
    chmod 0700 /var/lib/vikunja
    install -dm0700 -o pol-vikunja -g pol-vikunja /var/lib/vikunja/files
    install -dm0755 /etc/polarita-vikunja
'
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
incus file pull postgres-test/var/lib/polarita-postgres/pki/server.crt "$tmp/postgres.crt"
incus file pull gitea-test/etc/polarita-gitea/git-ca.crt "$tmp/git-ca.crt"
printf 'https://%s:8447/\n' "$host" >"$tmp/url"
incus file push --mode=0644 "$tmp"/{postgres.crt,git-ca.crt,url} "$src/start.py" vikunja-test/etc/polarita-vikunja/
"${inside[@]}" python3 - "$host" <<'PY'
import sys
from pathlib import Path
hosts = Path("/etc/hosts")
tag = "# polarita-vikunja-oidc"
lines = [line for line in hosts.read_text().splitlines() if not line.endswith(tag)]
lines.append(f"10.239.32.13 {sys.argv[1]} {tag}")
hosts.write_text("\n".join(lines) + "\n")
PY
bash "$src/../git/obnov-proxy.sh"
python3 "$src/../identita/sluzba_oidc.py" "$host" vikunja
incus file push --mode=0644 "$src/polarita-vikunja.service" vikunja-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable polarita-vikunja
"${inside[@]}" systemctl restart polarita-vikunja
"${inside[@]}" python3 - <<'PY'
import json, time
from urllib.request import urlopen
deadline = time.monotonic() + 240
while True:
    try:
        with urlopen("http://10.239.32.20:3456/api/v1/info", timeout=5) as res:
            info = json.load(res)
        auth = info["auth"]
        oidc = auth["openid_connect"]
        if (auth["local"]["enabled"] or auth["local"]["registration_enabled"] or not oidc["enabled"]
                or [p["key"] for p in oidc["providers"]] != ["keycloak"]):
            raise RuntimeError("Nesouhlasí nastavení přihlášení do úkolovníku")
        break
    except OSError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(4)
print("Vikunja je připravena přes PostgreSQL a jednotné přihlášení ředitelství.")
PY
