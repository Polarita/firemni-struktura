#!/bin/bash
# Základní systém, šifrované ZFS a jeho jednotka odemčení vznikají v bloku 1.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
mountpoint -q /srv/polarita
systemctl is-active --quiet polarita-zfs.service
zfs list polarita_zfs/data/incus >/dev/null
src=$(cd "$(dirname "$0")/incus" && pwd)
export DEBIAN_FRONTEND=noninteractive
if ! command -v incus >/dev/null || ! command -v tofu >/dev/null; then
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    cd "$tmp"
    curl -fsSLO https://pkgs.zabbly.com/key.asc
    curl -fsSLO https://get.opentofu.org/opentofu.gpg
    curl -fsSL https://packages.opentofu.org/opentofu/tofu/gpgkey | gpg --batch --dearmor -o opentofu-repo.gpg
    verify() {
        local fpr
        fpr=$(gpg --batch --show-keys --with-colons "$1" | awk -F: '$1=="pub"{key=1;next} key && $1=="fpr"{print $10; key=0}')
        [[ $fpr == "$2" ]]
    }
    verify key.asc 4EFC590696CB15B87C73A3AD82CC8797C838DCFD
    verify opentofu.gpg E3E6E43D84CB852EADB0051D0C0AF313E5FD9F80
    verify opentofu-repo.gpg F4AF70F66EAC4337EEECC97407D3DFCD4C61499F
    install -d /etc/apt/keyrings
    install -m644 key.asc /etc/apt/keyrings/zabbly.asc
    install -m644 opentofu*.gpg /etc/apt/keyrings/
    . /etc/os-release
    echo "deb [signed-by=/etc/apt/keyrings/zabbly.asc] https://pkgs.zabbly.com/incus/stable $VERSION_CODENAME main" > /etc/apt/sources.list.d/zabbly-incus-stable.list
    echo "deb [signed-by=/etc/apt/keyrings/opentofu.gpg,/etc/apt/keyrings/opentofu-repo.gpg] https://packages.opentofu.org/opentofu/tofu/any/ any main" > /etc/apt/sources.list.d/opentofu.list
    apt-get update
    apt-get install -y incus tofu nftables
fi
install -d /etc/systemd/system/incus.service.d
printf '%s\n' '[Unit]' 'Requires=polarita-zfs.service' 'After=polarita-zfs.service' > /etc/systemd/system/incus.service.d/polarita-storage.conf
systemctl daemon-reload
systemctl start incus.service
if ! incus storage show default >/dev/null 2>&1; then
    [[ -z $(incus storage list -f csv -c n) && -z $(incus list -f csv -c n) ]]
    incus admin init --preseed < "$src/preseed.yaml"
fi
[[ -z $(incus config get core.https_address) ]]
[[ $(incus storage get default source) == polarita_zfs/data/incus/pool ]]
for spec in 'docker https://docker.io' 'ghcr https://ghcr.io'; do
    read -r name url <<<"$spec"
    if ! incus remote list --format csv -c n | grep -Fxq "$name"; then
        incus remote add "$name" "$url" --protocol=oci
    fi
done
install -d /srv/polarita/infra/incus
cd /srv/polarita/infra/incus
for file in providers.tf preseed.yaml .terraform.lock.hcl; do
    [[ -f $file ]] || install -m644 "$src/$file" .
done
incus version
tofu version
