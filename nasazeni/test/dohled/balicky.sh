#!/bin/bash
# APT vyřeší závislosti vůči seznamu balíků cíle. Monitoring zůstává od internetu oddělený.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
inside=(incus exec -T checkmk-test --)
deb=/srv/polarita/infra/checkmk-test/zdroje/check-mk-community-2.5.0p21_0.resolute_amd64.deb
if "${inside[@]}" omd version 2>/dev/null | grep -q '2.5.0p21'; then exit 0; fi
tmp=$(mktemp -d)
stage=$("${inside[@]}" mktemp -d /var/tmp/polarita-checkmk-XXXXXXXX)
[[ $stage =~ ^/var/tmp/polarita-checkmk-[A-Za-z0-9]{8}$ ]]
trap 'rm -r -- "$tmp"; "${inside[@]}" rm -r -- "$stage"' EXIT
install -d -m 0755 "$tmp/deb/partial"
incus file pull checkmk-test/var/lib/dpkg/status "$tmp/status"
apt-get -o "Dir::State::status=$tmp/status" -o "Dir::Cache::archives=$tmp/deb" --download-only --no-install-recommends -y install "$deb"
tar -cf - -C "$tmp/deb" . | "${inside[@]}" tar -xf - -C "$stage"
incus file push --mode=0644 "$deb" "checkmk-test$stage/"
"${inside[@]}" bash -ec 'set -euo pipefail; d=$1; install -d -m 0755 "$d/lists/partial"; export DEBIAN_FRONTEND=noninteractive; apt-get -o Dir::State::Lists="$d/lists" -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- --no-install-recommends -y install "$d"/*.deb; omd version' install "$stage"
