#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
fqdn=${1:?Chybí jméno ředitelství}
[[ $fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
inside=(incus exec -T zulip-test --)
work=/srv/polarita/infra/zulip-test/conf
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
incus file pull gitea-test/var/lib/gitea/vstup/data/caddy/pki/authorities/local/root.crt "$work/identita.crt"
"${inside[@]}" install -m 0644 /etc/polarita-zulip/identita.crt /usr/local/share/ca-certificates/polarita-oidc.crt
"${inside[@]}" update-ca-certificates
"${inside[@]}" python3 - "$fqdn" <<'PY'
import json, sys, urllib.request
from pathlib import Path
p=Path("/etc/hosts")
tag="# polarita-oidc-test"
with p.open("r+") as stream:
    rows=[line for line in stream.read().splitlines() if not line.endswith(tag)]
    rows.append(f"10.239.32.13 {sys.argv[1]} {tag}")
    stream.seek(0)
    stream.write("\n".join(rows)+"\n")
    stream.truncate()
issuer="https://"+sys.argv[1]+"/identita/realms/polarita"
with urllib.request.urlopen(issuer+"/.well-known/openid-configuration",timeout=8) as response:
    if json.load(response).get("issuer")!=issuer:
        raise RuntimeError("Zulip nedosáhl na správnou identitu Keycloaku")
PY
touch "$work/pripraveno"
