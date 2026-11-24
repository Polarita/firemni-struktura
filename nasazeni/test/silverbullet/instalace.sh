#!/bin/bash
set -euo pipefail
umask 022
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/silverbullet-test
data=/srv/polarita/data/silverbullet-test
[[ $(findmnt -no SOURCE --mountpoint /srv/polarita/data) == polarita_zfs/data ]]
install -dm0755 "$work" "$work/tofu"
exec 9>"$work/.instalace"
flock 9
if ! zfs list -Ho name polarita_zfs/data/silverbullet-test >/dev/null 2>&1; then
    [[ ! -e $data ]]
    zfs create -o mountpoint="$data" -o devices=off -o setuid=off -o exec=off polarita_zfs/data/silverbullet-test
fi
[[ $(findmnt -no SOURCE --mountpoint "$data") == polarita_zfs/data/silverbullet-test ]]
[[ $(zfs get -Ho value encryptionroot polarita_zfs/data/silverbullet-test) == polarita_zfs ]]
install -dm0755 "$data/overene"
install -m0644 "$src/pohled.py" "$src/obnov.sh" "$work/"
python3 "$work/pohled.py"
python3 "$src/distribuce.py"
cd "$work/tofu"
install -m0644 "$src/silverbullet.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
bash "$src/../incus/tofu-init.sh"
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for item in json.load(sys.stdin).get("resource_changes",[]):
    a=item["change"]["actions"]
    if a not in (["no-op"],["read"]) and not (item["address"]=="incus_instance.silverbullet" and a in (["create"],["update"])):
        raise SystemExit("Neočekávaná změna "+item["address"])'
tofu apply -input=false "$tmp/plan"
inside=(incus exec -T silverbullet-test --)
"${inside[@]}" sh -ec 'for i in $(seq 1 60); do if test -S /run/systemd/private && mountpoint -q /var/lib/polarita-znalosti; then exit 0; fi; sleep 1; done; exit 1'
"${inside[@]}" sh -ec 'getent passwd pol-silverbullet >/dev/null || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin pol-silverbullet; install -dm0750 -o pol-silverbullet -g pol-silverbullet /var/lib/silverbullet
    /opt/polarita-silverbullet/silverbullet --version
    /opt/polarita-silverbullet/oauth2-proxy --version'
incus file push --mode 0644 "$src/polarita-silverbullet.service" silverbullet-test/etc/systemd/system/
"${inside[@]}" python3 - <<'PY'
import json,os
from pathlib import Path
base=Path("/var/lib/silverbullet")
spaces={"polarita":{"name":"Znalostní paměť Polarity","folder":"/var/lib/polarita-znalosti/current","binding":{"prefix":"/pamet"},"access":"read","readOnly":True,"shell":{"enabled":False},"indexPage":"00-Meta/pobocky"}}
for name,value in (("users.json",{}),("spaces.json",spaces)):
    p=base/name
    if p.exists():
        if json.loads(p.read_bytes())!=value:
            raise RuntimeError("Existující konfigurace se liší: "+name)
    else:
        tmp=p.with_suffix(".next")
        tmp.write_text(json.dumps(value,ensure_ascii=False))
        tmp.chmod(0o644)
        os.replace(tmp,p)
PY
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now polarita-silverbullet
"${inside[@]}" python3 - <<'PY'
from urllib.request import urlopen
import time
url="http://127.0.0.1:3000/pamet/.fs/00-Meta/pobocky.md"
for attempt in range(45):
    try:
        with urlopen(url,timeout=4) as r:
            assert r.status==200 and b"CZ-101" in r.read()
        break
    except OSError:
        if attempt==44: raise
        time.sleep(1)
print("SilverBullet vydal přes vlastní souborové API registr poboček z ověřeného znalostního Gitu.")
PY
install -m0644 "$src"/polarita-silverbullet-export.{timer,service} /etc/systemd/system/
systemctl daemon-reload
systemctl start polarita-silverbullet-export.service
systemctl enable --now polarita-silverbullet-export.timer
tofu plan -input=false -detailed-exitcode
