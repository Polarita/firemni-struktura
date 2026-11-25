#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-ocpp-instalace.lock
flock 8
run=(incus exec -T postgres-test --)
cache=/var/cache/polarita-distribuce/ocpp
install -dm0755 "$cache"
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
while read -r digest url; do
    [[ $digest =~ ^[a-f0-9]{64}$ && $url == https://files.pythonhosted.org/* ]]
    name=${url##*/}
    if ! (cd "$cache" && echo "$digest  $name" | sha256sum --check --status) 2>/dev/null; then
        curl -fsSL --retry 3 --max-time 90 --proto '=https' --proto-redir '=https' "$url" -o "$tmp/$name"
        (cd "$tmp" && echo "$digest  $name" | sha256sum -c --status)
        install -m0644 "$tmp/$name" "$cache/.$name.next"
        mv -T "$cache/.$name.next" "$cache/$name"
    fi
    cp "$cache/$name" "$tmp/$name"
done <"$src/kola.lock"
cp "$src"/{prijem.py,stanice.py,polarita-ocpp.service} "$tmp/"
rev=$(cd "$tmp" && sha256sum *.whl *.py *.service | sha256sum | cut -d' ' -f1)
base=/opt/polarita-ocpp-test
"${run[@]}" install -dm0755 "$base/$rev" /etc/polarita-ocpp-test
tar -C "$tmp" -cf - . | "${run[@]}" tar --no-overwrite-dir -xf - -C "$base/$rev"
export PYTHONPATH="$src/../revize:$src/../rozvadece"
python3 - <<'PY' >"$tmp/stanice.json"
from pas import rozvadec_spisu
from spisy_rz import id_spisu
import json
print(json.dumps({key:rozvadec_spisu(str(id_spisu(varianta)))[0]
                  for key,varianta in (("EV-TEST-01","kladny"),("EV-TEST-02","zaporny"))},sort_keys=True))
PY
incus file push --mode=0644 "$tmp/stanice.json" postgres-test/etc/polarita-ocpp-test/.stanice.next
"${run[@]}" bash -ec '
getent passwd pol_ocpp_test >/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin pol_ocpp_test
cfg=/etc/polarita-ocpp-test
changed=false
if ! cmp -s "$cfg/.stanice.next" "$cfg/stanice.json"; then changed=true; fi
mv -Tf "$cfg/.stanice.next" "$cfg/stanice.json"
if [[ $(readlink "$1/current" || true) != "$2" ]]; then changed=true; fi
ln -sfn "$2" "$1/.current.next"
mv -Tf "$1/.current.next" "$1/current"
install -m0644 "$1/current/polarita-ocpp.service" /etc/systemd/system/polarita-ocpp.service
systemctl daemon-reload
systemctl enable polarita-ocpp.service
if "$changed"; then systemctl restart polarita-ocpp.service; else systemctl start polarita-ocpp.service; fi
for i in {1..30}; do [[ -S /run/polarita-ocpp-test/prijem.sock ]] && break; sleep 1; done
systemctl is-active --quiet polarita-ocpp.service
python3 -I "$1/current/stanice.py"
' -- "$base" "$rev"
