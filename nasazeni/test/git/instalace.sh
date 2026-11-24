#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
url=${1:?Chybí soukromá HTTPS adresa Gitea}
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/gitea-test
store=/srv/polarita/data/gitea
[[ $(findmnt -n -o SOURCE --mountpoint "$store") == polarita_zfs/data/gitea ]]
[[ $(zfs get -H -o value encryption polarita_zfs/data/gitea) == aes-256-gcm ]]
bash "$src/distribuce.sh"
install -d -m 0755 "$work/tofu" "$store/test"
exec 9>"$work/.instalace"
flock 9
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
cd "$work/tofu"
install -m 0644 "$src/gitea.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
bash "$src/../incus/tofu-init.sh"
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for item in json.load(sys.stdin).get("resource_changes", []):
    actions=item["change"]["actions"]
    if actions in (["no-op"], ["read"]): continue
    if item["address"] == "incus_instance.gitea" and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + item["address"])'
tofu apply -input=false "$tmp/plan"
inside=(incus exec -T gitea-test --)
"${inside[@]}" sh -ec 'for i in $(seq 1 60); do if test -S /run/systemd/private && mountpoint -q /var/lib/gitea; then exit 0; fi; sleep 1; done; exit 1'
bash "$src/../incus/balicky.sh" gitea-test git=1:2.53.0-1ubuntu1.1
"${inside[@]}" bash -ec '
getent group gitea-test >/dev/null || groupadd --gid 17307 gitea-test
getent passwd gitea-test >/dev/null || useradd --uid 17307 --gid gitea-test --no-create-home --home-dir /var/lib/gitea/home --shell /usr/sbin/nologin gitea-test
[[ $(id -u gitea-test) == 17307 && $(id -g gitea-test) == 17307 ]]
install -d -m 0700 -o gitea-test -g gitea-test /var/lib/gitea/{home,git,data}
install -d -m 0755 /etc/polarita-gitea
git --version
/opt/gitea/gitea-28.4.0-linux-amd64 --version'
tofu plan -input=false -detailed-exitcode
echo "$url" >"$tmp/url"
incus file push --mode=0644 "$src/app.py" "$tmp/url" gitea-test/etc/polarita-gitea/
incus file push --mode=0644 /srv/polarita/infra/postgres-test/ca.crt gitea-test/etc/polarita-gitea/ca-postgres.crt
incus file push --mode=0644 "$src/gitea-test.service" gitea-test/etc/systemd/system/
"${inside[@]}" systemctl daemon-reload
"${inside[@]}" bash -ec 'install -d -m 0700 -o gitea-test -g gitea-test /var/lib/gitea/home/.postgresql; install -m 0444 /etc/polarita-gitea/ca-postgres.crt /var/lib/gitea/home/.postgresql/root.crt'
