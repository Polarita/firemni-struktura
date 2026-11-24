#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
dir=/srv/polarita/infra/checkmk-test/zdroje
install -d -m 0750 "$dir"
cd "$dir"
version=2.5.0p21
deb=check-mk-community-${version}_0.resolute_amd64.deb
digest=1c0b8dc37dc6afe69b9165b657e141e5b37381e6fb2f84f95a8c638654b58309
tmp=$(mktemp -d -p "$dir")
trap 'rm -r -- "$tmp"' EXIT
if ! echo "$digest  $deb" | sha256sum --check --status; then
    curl --retry 3 --max-time 480 -fsSL "https://download.checkmk.com/checkmk/$version/$deb" -o "$tmp/$deb"
    (cd "$tmp"; echo "$digest  $deb" | sha256sum --check --status)
    mv -T "$tmp/$deb" "$deb"
fi
if [[ ! -s podpis-vyrobce.gpg ]]; then
    curl --retry 2 --max-time 45 -fsSL https://download.checkmk.com/checkmk/Check_MK-pubkey.gpg -o "$tmp/klic"
    mv "$tmp/klic" podpis-vyrobce.gpg
fi
gpg --batch --no-autostart --dearmor <podpis-vyrobce.gpg >"$tmp/keyring.gpg"
gpgv --homedir "$tmp" --keyring "$tmp/keyring.gpg" --status-fd 1 "$deb" | awk '$2=="VALIDSIG" && $NF=="B1E7106575B723F00611C612434DAC48C4503261" {valid=1} END {exit !valid}'
[[ $(dpkg-deb -f "$deb" Package) == "check-mk-community-$version" && $(dpkg-deb -f "$deb" Version) == 0.resolute ]]
