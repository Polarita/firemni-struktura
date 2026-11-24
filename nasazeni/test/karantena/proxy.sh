#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/karantena-test/priprava/haproxy
target=/opt/polarita-clamav-proxy
version=3.2.25-0ubuntu0.26.04.2
install -d -m 0755 "$work/deb/partial" "$target"
if [[ ! -e $target/.verze || $(cat "$target/.verze") != "$version" ]]; then
    apt-get -o "Dir::Cache::archives=$work/deb" --download-only --no-install-recommends -y install "haproxy=$version"
    if ! compgen -G "$work/deb/haproxy_*.deb" >/dev/null; then
        (cd "$work/deb" && apt-get download "haproxy=$version")
    fi
    for f in "$work"/deb/*.deb; do dpkg-deb -x "$f" "$target"; done
    echo "$version" >"$target/.verze"
fi
install -m 0644 "$src/clamav-proxy.cfg" /etc/polarita/clamav-proxy.cfg
LD_LIBRARY_PATH="$target/usr/lib/x86_64-linux-gnu" "$target/usr/sbin/haproxy" -c -f /etc/polarita/clamav-proxy.cfg
install -m 0644 "$src/polarita-clamav-proxy.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-clamav-proxy.service
systemctl restart polarita-clamav-proxy.service
systemctl is-active --quiet polarita-clamav-proxy.service
