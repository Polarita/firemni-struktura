#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
fqdn=${1:?Chybí jméno ředitelství}
[[ $fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
inside=(incus exec -T zulip-test --)
work=/srv/polarita/infra/zulip-test/conf
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
incus file pull valkey-test/run/secrets/valkey-cert "$tmp/valkey.crt"
openssl verify -CAfile "$tmp/valkey.crt" -verify_ip 10.239.33.13 "$tmp/valkey.crt"
install -m 0644 "$tmp/valkey.crt" "$work/valkey.crt"
python3 "$src/identita.py" "$fqdn"
bash "$src/nastav-frontu.sh"
incus exec -T postgres-test -- runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -d postgres <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname='zulip' AND datcollate='C.UTF-8' AND datctype='C.UTF-8' AND encoding=pg_char_to_encoding('UTF8')) THEN
        RAISE EXCEPTION 'Nekompatibilní řazení databáze zulip';
    END IF;
END $$;
ALTER DATABASE zulip OWNER TO zulip;
SQL
incus file pull gitea-test/var/lib/gitea/vstup/data/caddy/pki/authorities/local/root.crt "$tmp/identita.crt"
openssl x509 -in "$tmp/identita.crt" -noout -checkend 0
install -m 0644 "$tmp/identita.crt" "$work/.identita.crt.next"
mv -T "$work/.identita.crt.next" "$work/identita.crt"
"${inside[@]}" install -m 0644 /etc/polarita-zulip/identita.crt /usr/local/share/ca-certificates/polarita-oidc.crt
"${inside[@]}" update-ca-certificates
"${inside[@]}" python3 - "$fqdn" <<'PY'
import json, socket, sys, urllib.request
if set(socket.gethostbyname_ex(sys.argv[1])[2]) != {"10.239.32.13"}:
    raise RuntimeError("Zulip nepoužívá vnitřní adresu firemní identity")
issuer="https://"+sys.argv[1]+"/identita/realms/polarita"
with urllib.request.urlopen(issuer+"/.well-known/openid-configuration",timeout=8) as response:
    if json.load(response).get("issuer")!=issuer:
        raise RuntimeError("Zulip nedosáhl na správnou identitu Keycloaku")
PY
touch "$work/pripraveno"
