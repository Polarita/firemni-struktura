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
bash "$src/hosts.sh" "$host" "$work/conf"
# /s6-init je soubor připojený Incusem při startu. Starší verze ještě nepřebírala /etc/hosts.
if ! cmp -s "$src/start.sh" "$work/conf/start.sh" || [[ ! -x $work/conf/start.sh ]]; then
    install -m0755 "$src/start.sh" "$work/conf/start.sh.next"
    mv -T "$work/conf/start.sh.next" "$work/conf/start.sh"
fi
[[ $(incus config get paperless-test user.polarita.role) == paperless-test ]]
state=$(incus query /1.0/instances/paperless-test/state | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
if [[ $state == Stopped ]]; then
    incus start paperless-test
fi
# Po studeném startu je /run v RAM a agent musí znovu dodat strojové údaje.
if ! "${inside[@]}" sh -ec 'test -s /run/secrets/pg-paperless && test -s /run/secrets/paperless-secret && test -s /run/secrets/paperless-oidc_secret'; then
    python3 "$src/../trezor/agenti.py" --klient paperless-test
fi
bash "$src/../git/obnov-proxy.sh"
python3 "$src/../identita/sluzba_oidc.py" "$host" paperless
# Převezme novou tabulku také při aktualizaci už běžící instance.
"${inside[@]}" sh -ec 'cmp -s /etc/polarita-paperless/hosts /etc/hosts || mount --bind /etc/polarita-paperless/hosts /etc/hosts'
"${inside[@]}" python3 -c 'import socket, sys; assert {r[4][0] for r in socket.getaddrinfo(sys.argv[1],443)} == {"10.239.32.13"}' "$host"
reload="$work/.web-reload"
# Při první instalaci čeká PID 1 na web.sh. Publikuj ho až po všech konfiguracích.
for file in postgres.crt oidc.crt url polarita_settings.py web.py web.sh; do
    from="$tmp/$file"
    mode=0644
    case $file in *.py|web.sh) from="$src/$file" ;; esac
    if [[ $file == web.sh ]]; then mode=0755; fi
    if ! cmp -s "$from" "$work/conf/$file" || [[ $file == web.sh && ! -x $work/conf/web.sh ]]; then
        if [[ -x $work/conf/web.sh ]]; then touch "$reload"; fi
        install -m"$mode" "$from" "$work/conf/$file.next"
        mv -T "$work/conf/$file.next" "$work/conf/$file"
    fi
done
if [[ -e $reload ]]; then
    incus restart paperless-test
    python3 "$src/../trezor/agenti.py" --klient paperless-test
fi
bash "$src/../karantena/pamet-fronty.sh"
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
# Připravenost zahrnuje i DNS a TLS pro přihlášení po startu nové instance.
"${inside[@]}" /command/with-contenv /command/s6-setuidgid paperless python3 - "$host" <<'CHECK'
import socket, sys, time
import requests

host = sys.argv[1]
issuer = f"https://{host}/identita/realms/polarita"
deadline = time.monotonic() + 120
while True:
    try:
        if {r[4][0] for r in socket.getaddrinfo(host, 443)} != {"10.239.32.13"}:
            raise RuntimeError("Archiv nerozpoznal soukromou adresu Keycloaku.")
        response = requests.get(issuer + "/.well-known/openid-configuration", timeout=(10, 30), allow_redirects=False)
        if response.status_code == 200 and response.json().get("issuer") == issuer:
            break
    except (socket.gaierror, requests.RequestException):
        pass
    if time.monotonic() >= deadline:
        raise RuntimeError("Archiv po spuštění nepotvrdil poskytovatele přihlášení.")
    time.sleep(4)
print("Archiv po spuštění ověřil adresu a TLS poskytovatele přihlášení.")
CHECK
if [[ -e $reload ]]; then unlink "$reload"; fi
