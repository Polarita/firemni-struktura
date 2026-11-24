#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/restic-test
store=/srv/polarita/backups/restic-test
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/backups) == polarita_zfs/backups ]]
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
if ! zfs list -Ho name polarita_zfs/backups/restic-test >/dev/null 2>&1; then
    [[ ! -e $store ]]
    zfs create -o mountpoint="$store" -o exec=off -o setuid=off -o devices=off polarita_zfs/backups/restic-test
fi
if [[ $(zfs get -Ho value mounted polarita_zfs/backups/restic-test) == no ]]; then zfs mount polarita_zfs/backups/restic-test; fi
[[ $(findmnt -n -o SOURCE --mountpoint "$store") == polarita_zfs/backups/restic-test ]]
[[ $(zfs get -Ho value encryptionroot polarita_zfs/backups/restic-test) == polarita_zfs ]]
export DEBIAN_FRONTEND=noninteractive
if [[ $(dpkg-query -W -f='${Status} ${Version}' restic 2>/dev/null || true) != 'install ok installed 0.18.1-3ubuntu1' ]]; then
    apt-get -o DPkg::Lock::Timeout=120 --no-install-recommends -y install restic=0.18.1-3ubuntu1
fi
cd "$work/tofu"
install -m 0644 "$src/restic.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
tofu init -input=false -lockfile=readonly
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    a=r["change"]["actions"]
    if a in (["no-op"],["read"]) or (r["address"]=="incus_instance.zaloha" and a in (["create"],["update"])): continue
    sys.exit("Neočekávaná změna "+r["address"])'
tofu apply -input=false "$tmp/plan"
inside=(incus exec -T restic-test --)
"${inside[@]}" sh -ec 'for i in $(seq 1 60); do if test -S /run/systemd/private && mountpoint -q /var/lib/restic-test; then exit 0; fi; sleep 1; done; exit 1'
bash "$src/../incus/balicky.sh" restic-test restic-rest-server=0.14.0-1
"${inside[@]}" bash -ec '
getent passwd pol-restic >/dev/null || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin pol-restic
install -d -m 0700 -o pol-restic -g pol-restic /var/lib/restic-test/data
install -d -m 0750 -o root -g pol-restic /etc/polarita-restic
cd /etc/polarita-restic
if [[ ! -s server.key ]]; then
    umask 077
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out server.key.next
    mv -T server.key.next server.key
fi
if [[ ! -s server.crt ]] || ! openssl x509 -checkend 2592000 -noout -in server.crt; then
    openssl req -new -x509 -key server.key -days 365 -subj /CN=restic.polarita.test -addext subjectAltName=IP:10.239.33.15,DNS:restic.polarita.test -addext extendedKeyUsage=serverAuth -out server.crt.next
    mv -T server.crt.next server.crt
fi
chown root:pol-restic server.key
chmod 0640 server.key
chmod 0644 server.crt'
python3 "$src/pristup.py"
incus file push --mode=0644 "$src/restic-test.service" restic-test/etc/systemd/system/
incus file pull restic-test/etc/polarita-restic/server.crt "$work/server.crt"
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" systemctl enable --now restic-test.service
"${inside[@]}" systemctl restart restic-test.service
for i in {1..20}; do
    code=$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 2 --cacert "$work/server.crt" https://10.239.33.15:8443/polarita-test/firma/config || true)
    if [[ $code == 401 ]]; then break; fi
    sleep 1
done
[[ $code == 401 ]]
tofu plan -input=false -detailed-exitcode
echo 'Restic TEST běží uvnitř polarita-hq. TLS ověřilo jméno serveru a anonymní čtení bylo odmítnuto.'
