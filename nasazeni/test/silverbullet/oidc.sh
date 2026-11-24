#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T silverbullet-test --)
"${inside[@]}" install -dm0755 /etc/polarita-silverbullet
fqdn=$(python3 "$src/identita.py")
[[ $fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
incus file pull gitea-test/etc/polarita-gitea/git-ca.crt "$tmp/git-ca.crt"
issuer=https://$fqdn/identita/realms/polarita
printf 'ISSUER=%s\nCALLBACK=https://%s:8446/pamet/oauth2/callback\n' "$issuer" "$fqdn" >"$tmp/proxy.env"
printf '%s\n' spravce@polarita.test >"$tmp/ucty"
incus file push --mode=0644 "$tmp"/{proxy.env,ucty,git-ca.crt} silverbullet-test/etc/polarita-silverbullet/
"${inside[@]}" python3 - "$fqdn" <<'PY'
import os,sys
from pathlib import Path
p = Path("/etc/hosts")
tag = "# polarita-silverbullet-oidc"
rows = [line for line in p.read_text().splitlines() if not line.endswith(tag)]
rows.append(f"10.239.32.13 {sys.argv[1]} {tag}")
with p.open("r+") as f:
    f.seek(0)
    f.write("\n".join(rows)+"\n")
    f.truncate()
    f.flush()
    os.fsync(f.fileno())
PY
"${inside[@]}" python3 - "$issuer" <<'PY'
import json, ssl, sys
from urllib.request import urlopen
ctx = ssl.create_default_context(cafile="/etc/polarita-silverbullet/git-ca.crt")
with urlopen(sys.argv[1]+"/.well-known/openid-configuration",context=ctx,timeout=8) as res:
    assert json.load(res)["issuer"] == sys.argv[1]
PY
"${inside[@]}" bash -se <"$src/pristup.sh"
incus file push --mode=0644 "$src/polarita-silverbullet-oidc.service" silverbullet-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable polarita-silverbullet-oidc
"${inside[@]}" systemctl restart polarita-silverbullet-oidc
"${inside[@]}" python3 - <<'PY'
from time import monotonic, sleep
from urllib.request import urlopen
# První TLS spojení s identitou při souběžném sestavení může vyžadovat
# automatický restart proxy. Připravenost určuje až odpověď služby.
deadline = monotonic() + 240
while True:
    try:
        with urlopen("http://10.239.32.19:4180/ping", timeout=4) as r:
            assert r.status == 200
        break
    except OSError:
        if monotonic() >= deadline:
            raise
        sleep(3)
PY
