#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
base=/srv/polarita/infra/hrana/conf/obchod
build=/srv/polarita/apps/web-polarita-cz/current/dist/obchod
exec 9>/run/polarita-obchod-web.lock
flock 9
install -dm0755 "$base/releases"
tmp=$(mktemp -d "$base/.stranka-XXXXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
install -m0644 "$build/index.html" "$build/nakup.js" "$tmp/"
incus exec -T medusa-test -- cat /var/lib/polarita-medusa-test/katalog.json | python3 -c '
import json,re,sys
v=json.load(sys.stdin)
fields={"publishable":"pk_","region_id":"reg_","product_id":"prod_","shipping_option_id":"so_"}
if set(v)!=set(fields) or not all(isinstance(v[k],str) and re.fullmatch(p+"[A-Za-z0-9_]+",v[k]) for k,p in fields.items()):
    sys.exit("Neplatná veřejná konfigurace obchodu.")
print(json.dumps(v,sort_keys=True))' >"$tmp/katalog.json"
chmod 0644 "$tmp/katalog.json"
rev=$(cd "$tmp" && sha256sum index.html nakup.js katalog.json | sha256sum | cut -d' ' -f1)
if [[ ! -d $base/releases/$rev ]]; then
    chmod 0755 "$tmp"
    mv -T "$tmp" "$base/releases/$rev"
fi
ln -sfn "releases/$rev" "$base/.current-next"
mv -Tf "$base/.current-next" "$base/current"
bash "$src/../hrana/obnov-vstup.sh"
