#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/karantena-test
vm=karantena-test
exec 9>"$work/.instalace"
flock 9
[[ $(incus config get "$vm" user.polarita.role) == "$vm" ]]
if [[ $(incus list "$vm" -c s -f csv) != STOPPED ]]; then
    echo 'Pracovní VM už zpracovává úlohu.' >&2
    exit 1
fi
python3 "$src/balicek.py" "$work/priprava"
incus start "$vm"
trap 'incus stop "$vm" --timeout 60 </dev/null' EXIT
for i in {1..120}; do
    if incus exec -T "$vm" -- true 2>/dev/null; then break; fi
    sleep 1
done
incus exec -T "$vm" -- bash -ec 'test "$(ls /sys/class/net)" = lo; test -z "$(ip route show)"; install -d -m 0700 /var/cache/karantena-deb'
if incus exec -T "$vm" -- bash -ec 'test "$(dpkg-query -W -f="\${db:Status-Status} \${Version}" dangerzone-full 2>/dev/null)" = "installed 0.11.1"; command -v dangerzone-cli; command -v clamscan; command -v qpdf; command -v pdfimages'; then
    exit 0
fi
incus file pull "$vm/var/lib/dpkg/status" "$work/priprava/status"
cache=$work/priprava/zavislosti
install -d -m 0755 "$cache/partial"
apt-get -o "Dir::State::status=$work/priprava/status" -o "Dir::Cache::archives=$cache" \
    --no-install-recommends --download-only -y install "$work/priprava/dangerzone-full_0.11.1_amd64.deb" \
    clamav=1.5.4+dfsg-0ubuntu0.26.04.1 qpdf=12.3.2-1 poppler-utils=26.01.0-2ubuntu0.3
incus file push "$work/priprava/dangerzone-full_0.11.1_amd64.deb" "$vm/var/cache/karantena-deb/"
shopt -s nullglob
deps=("$cache"/*.deb)
if (( ${#deps[@]} )); then
    tar cf - -C "$cache" . | incus exec -T "$vm" -- tar xf - -C /var/cache/karantena-deb
fi
incus exec -T "$vm" -- bash -ec '
export DEBIAN_FRONTEND=noninteractive
mkdir -p /run/karantena-seznam/partial
apt-get install -y --no-install-recommends -o Dir::State::Lists=/run/karantena-seznam -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- /var/cache/karantena-deb/*.deb
dpkg-query -W dangerzone-full podman clamav qpdf
command -v dangerzone-cli
test "$(ls /sys/class/net)" = lo
rm -rf -- /var/cache/karantena-deb'
