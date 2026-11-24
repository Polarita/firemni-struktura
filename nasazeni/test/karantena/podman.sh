#!/bin/bash
# Doplňky pro Podman pod samostatným účtem v bezsíťovém systému.
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
vm=karantena-test
if incus exec -T "$vm" -- sh -ec 'command -v newuidmap && command -v newgidmap && command -v pasta && command -v fuse-overlayfs && dpkg-query -W dbus-user-session' >/dev/null; then
    exit 0
fi
work=/srv/polarita/infra/karantena-test/priprava/rootless
install -d -m 0755 "$work/deb/partial"
incus file pull "$vm/var/lib/dpkg/status" "$work/status"
apt-get -o "Dir::State::status=$work/status" -o "Dir::Cache::archives=$work/deb" \
    --no-install-recommends --download-only -y install uidmap=1:4.17.4-2ubuntu3 fuse-overlayfs=1.14-1build2 \
    passt=0.0~git20260120.386b5f5-1 dbus-user-session=1.16.2-2ubuntu4
incus exec -T "$vm" -- install -d -m 0700 /var/cache/polarita-rootless
tar cf - -C "$work/deb" . | incus exec -T "$vm" -- tar xf - -C /var/cache/polarita-rootless
incus exec -T "$vm" -- bash -ec '
mkdir -p /run/karantena-seznam/partial
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends -o Dir::State::Lists=/run/karantena-seznam -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- /var/cache/polarita-rootless/*.deb
rm -rf -- /var/cache/polarita-rootless'
