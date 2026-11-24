#!/bin/bash
# Zveřejní oba zašifrované tvary téhož nového klíče jediným přejmenováním.
set -euo pipefail
umask 077
dest=${1:?}
recipient=${2:?}
[[ $EUID == 0 && $(hostname -s) == polarita-hq && -c /dev/tpmrm0 ]]
if [[ -d $dest ]]; then
    cmp -s "$recipient" "$dest/prijemce.crt"
    [[ -s $dest/vtpm.cred && -s $dest/obnova.cms ]]
    exit 0
fi
tmp=$(mktemp -d -p "$(dirname "$dest")" .zfs-material.XXXXXXXX)
ram=$(mktemp -d -p /run polarita-zfs.XXXXXXXX)
trap 'rm -rf -- "$ram" "$tmp"' EXIT
[[ $(findmnt -n -T "$ram" -o FSTYPE) == tmpfs ]]
openssl rand -hex 32 > "$ram/key"
systemd-creds encrypt --with-key=tpm2 --tpm2-pcrs=7 --name=polarita-zfs.key "$ram/key" "$tmp/vtpm.cred"
openssl cms -encrypt -binary -aes-256-cbc -outform DER -in "$ram/key" -out "$tmp/obnova.cms" "$recipient"
install -m 0600 "$recipient" "$tmp/prijemce.crt"
systemd-creds decrypt --name=polarita-zfs.key "$tmp/vtpm.cred" - | cmp -s "$ram/key" -
mv -T "$tmp" "$dest"
