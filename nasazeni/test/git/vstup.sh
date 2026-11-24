#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
url=$1
name=$(python3 - "$url" <<'PY'
from urllib.parse import urlsplit
import sys,re
u=urlsplit(sys.argv[1])
if u.scheme!="https" or u.path!="/git/" or not re.fullmatch(r"[a-z0-9.-]+",u.netloc) or not u.hostname:
    raise ValueError("Neplatná adresa Gitea")
print(u.hostname)
PY
)
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
bin=/srv/polarita/infra/gitea-test/bin
src_bin=/srv/polarita/infra/garage-test/bin/caddy
echo "a563843e11cbce39c557bd429ebb787d56f49d51d9bbb3292cd9b36b37a60cdf  $src_bin" | sha256sum --check --status
install -m 0755 "$src_bin" "$bin/caddy"
echo "POLARITA_GIT_HOST=$name" >"$tmp/vstup.env"
inside=(incus exec -T gitea-test --)
"${inside[@]}" bash -ec '
getent group gitea-vstup >/dev/null || groupadd --gid 17309 gitea-vstup
getent passwd gitea-vstup >/dev/null || useradd --uid 17309 --gid gitea-vstup --no-create-home --home-dir /var/lib/gitea/vstup --shell /usr/sbin/nologin gitea-vstup
[[ $(id -u gitea-vstup) == 17309 && $(id -g gitea-vstup) == 17309 ]]
install -d -m 0700 -o gitea-vstup -g gitea-vstup /var/lib/gitea/vstup
install -d -m 0755 /etc/polarita-gitea'
incus file push --mode=0644 "$tmp/vstup.env" "$src/Caddyfile" gitea-test/etc/polarita-gitea/
incus file push --mode=0644 "$src/gitea-vstup.service" gitea-test/etc/systemd/system/
"${inside[@]}" env "POLARITA_GIT_HOST=$name" /opt/gitea/caddy validate --config /etc/polarita-gitea/Caddyfile --adapter caddyfile
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now gitea-vstup.service
"${inside[@]}" systemctl restart gitea-vstup.service
cert=/var/lib/gitea/vstup/data/caddy/pki/authorities/local/root.crt
for i in {1..35}; do if "${inside[@]}" test -s "$cert"; then break; fi; sleep 1; done
incus file pull "gitea-test$cert" "$tmp/git-ca.crt"
for vm in gitea-test gitea-runner-test; do
    addr=10.239.32.13
    if [[ $vm == gitea-test ]]; then addr=127.0.0.1; fi
    incus exec -T "$vm" -- install -d -m 0755 /etc/polarita-gitea
    incus file push --mode=0644 "$tmp/git-ca.crt" "$vm/etc/polarita-gitea/git-ca.crt"
    incus exec -T "$vm" -- python3 - "$name" "$addr" <<'PY'
import os,sys
from pathlib import Path
p=Path("/etc/hosts")
tag="# polarita-gitea-test"
rows=[line for line in p.read_text().splitlines() if not line.endswith(tag)]
rows.append(f"{sys.argv[2]} {sys.argv[1]} {tag}")
with p.open("r+") as f:
    f.seek(0); f.write("\n".join(rows)+"\n"); f.truncate(); f.flush(); os.fsync(f.fileno())
PY
done
"${inside[@]}" python3 - "$name" <<'PY'
import json,ssl,sys
from urllib.request import urlopen
u="https://"+sys.argv[1]+"/identita/realms/polarita"
ctx=ssl.create_default_context(cafile="/etc/polarita-gitea/git-ca.crt")
with urlopen(u+"/.well-known/openid-configuration", context=ctx, timeout=7) as r:
    assert json.load(r)["issuer"]==u
print("Gitea přečetla discovery Keycloaku přes interní HTTPS se shodným veřejným názvem.")
PY
