#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
host=${1:?Chybí jméno ředitelství}
[[ $host =~ ^[a-z0-9.-]+\.ts\.net$ ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/paperless-test
exec 9>"$work/.instalace"
flock 9
inside=(incus exec -T paperless-test --)
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
nft -c -f "$src/vstup.nft"
install -m0644 "$src/vstup.nft" /etc/polarita/paperless.nft
install -m0644 "$src/polarita-paperless-sit.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-paperless-sit.service
systemctl restart polarita-paperless-sit.service
incus file pull postgres-test/var/lib/polarita-postgres/pki/server.crt "$tmp/postgres.crt"
incus file pull gitea-test/etc/polarita-gitea/git-ca.crt "$tmp/oidc.crt"
printf 'https://%s:8448\n' "$host" >"$tmp/url"
bash "$src/../git/obnov-proxy.sh"
python3 "$src/../identita/sluzba_oidc.py" "$host" paperless
"${inside[@]}" python3 - "$host" <<'PY'
from pathlib import Path
import sys
p=Path("/etc/hosts")
tag="# polarita-paperless-oidc"
rows=[row for row in p.read_text().splitlines() if not row.endswith(tag)]
p.write_text("\n".join([*rows, f"10.239.32.13 {sys.argv[1]} {tag}"])+"\n")
PY
restart=false
for file in postgres.crt oidc.crt url web.py; do
    from="$tmp/$file"
    [[ $file != web.py ]] || from="$src/web.py"
    if ! cmp -s "$from" "$work/conf/$file"; then
        install -m0644 "$from" "$work/conf/$file.next"
        mv -T "$work/conf/$file.next" "$work/conf/$file"
        restart=true
    fi
done
# První start čeká na zveřejnění web.sh. Při aktualizaci převezme služba novou konfiguraci po restartu.
if [[ -x $work/conf/web.sh ]]; then
    if ! cmp -s "$src/web.sh" "$work/conf/web.sh"; then restart=true; fi
else
    restart=false
fi
install -m0755 "$src/web.sh" "$work/conf/web.sh.next"
mv -T "$work/conf/web.sh.next" "$work/conf/web.sh"
if [[ $restart == true ]]; then incus restart paperless-test; fi
"${inside[@]}" python3 - "$host" <<'PY'
from http.client import HTTPConnection
import sys, time
deadline=time.monotonic()+900
while True:
    conn=HTTPConnection("10.239.32.21",8000,timeout=6)
    try:
        conn.request("GET","/api/documents/",headers={"Host":sys.argv[1]+":8448","X-Forwarded-Proto":"https"})
        r=conn.getresponse()
        if r.status in (401,403):
            break
    except OSError:
        pass
    finally:
        conn.close()
    if time.monotonic()>=deadline:
        raise RuntimeError("Dokumentové rozhraní neposkytlo očekávanou odpověď")
    time.sleep(4)
print("Anonymní čtení dokumentů vyžaduje přihlášení do Paperless.")
PY
