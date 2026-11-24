#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
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
tofu init -input=false -lockfile=readonly
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
version=1:2.53.0-1ubuntu1.1
if ! "${inside[@]}" dpkg-query -W '-f=${Version}' git 2>/dev/null | grep -Fxq "$version"; then
    incus file pull gitea-test/var/lib/dpkg/status "$tmp/status"
    install -d -m 0755 "$tmp/deb/partial"
    apt-get -o "Dir::State::status=$tmp/status" -o "Dir::Cache::archives=$tmp/deb" --download-only --no-install-recommends -y install "git=$version"
    "${inside[@]}" install -d -m 0755 /run/gitea-deb/lists/partial
    tar -cf - -C "$tmp/deb" . | "${inside[@]}" tar -xf - -C /run/gitea-deb
    "${inside[@]}" sh -ec 'DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends -o Dir::State::Lists=/run/gitea-deb/lists -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- install /run/gitea-deb/*.deb'
fi
"${inside[@]}" bash -ec '
getent group gitea-test >/dev/null || groupadd --gid 17307 gitea-test
getent passwd gitea-test >/dev/null || useradd --uid 17307 --gid gitea-test --no-create-home --home-dir /var/lib/gitea/home --shell /usr/sbin/nologin gitea-test
[[ $(id -u gitea-test) == 17307 && $(id -g gitea-test) == 17307 ]]
install -d -m 0700 -o gitea-test -g gitea-test /var/lib/gitea/{home,git,data}
install -d -m 0755 /etc/polarita-gitea
git --version
/opt/gitea/gitea-28.4.0-linux-amd64 --version'
tofu plan -input=false -detailed-exitcode
