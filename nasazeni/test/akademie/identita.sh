#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
host=${1:?Chybí název TEST}
[[ $host =~ ^[a-z0-9.-]+[.]ts[.]net$ ]]
inside=(incus exec -T akademie-test --)
exec 8>/run/polarita-akademie-identita.lock
flock 8
tmp=$(mktemp)
trap 'unlink "$tmp"' EXIT
incus exec -T gitea-test -- cat /etc/polarita-gitea/git-ca.crt >"$tmp"
openssl x509 -noout -checkend 0 -in "$tmp" >/dev/null
incus file push --mode=0644 "$tmp" akademie-test/usr/local/share/ca-certificates/polarita-oidc.crt
"${inside[@]}" update-ca-certificates
"${inside[@]}" python3 - "$host" <<'PY'
from pathlib import Path
import sys
p = Path('/etc/hosts')
tag = '# polarita-akademie-oidc'
entries = [line for line in p.read_text().splitlines() if not line.endswith(tag)]
entries.append(f'10.239.32.13 {sys.argv[1]} {tag}')
p.write_text('\n'.join(entries) + '\n')
PY
bash "$src/../git/obnov-proxy.sh"
python3 "$src/../identita/sluzba_oidc.py" "$host" moodle
"${inside[@]}" python3 - "$host" <<'PY'
import json
import sys
from urllib.error import HTTPError
from urllib.request import urlopen
origin = 'https://' + sys.argv[1]
issuer = origin + '/identita/realms/polarita'
with urlopen(issuer + '/.well-known/openid-configuration', timeout=20) as response:
    doc = json.load(response)
assert doc['issuer'] == issuer
for field, path in [('authorization_endpoint', 'auth'), ('token_endpoint', 'token'), ('userinfo_endpoint', 'userinfo'), ('jwks_uri', 'certs')]:
    if doc.get(field) != f'{issuer}/protocol/openid-connect/{path}':
        raise RuntimeError('Metadata neposkytla očekávanou cestu realmu.')
try:
    urlopen(origin + '/git/', timeout=20)
except HTTPError as error:
    if error.code != 403:
        raise
else:
    raise RuntimeError('Interní vstup Akademie zpřístupnil Git.')
print('Kontejner Moodle ověřil TLS a koncové body Keycloaku. Soukromý Git přístup z Akademie odmítl.')
PY
