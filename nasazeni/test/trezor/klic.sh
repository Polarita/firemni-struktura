#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
umask 077
work=/srv/polarita/infra/openbao-test
dir=/srv/polarita/data/bootstrap-test/openbao-test
install -d -m 0700 "$dir"
cd "$dir"
test -s "$work/test-obnova.crt"
tmp=$(mktemp -d /run/polarita-bao-key-XXXXXXXX)
trap 'rm -rf "$tmp"' EXIT
[[ $(findmnt -n -o FSTYPE -T "$tmp") == tmpfs ]]
if [[ ! -s pecet.cred ]]; then
    [[ ! -e pecet.cms && ! -e inicializovano ]]
    incus exec openbao-test -- test ! -e /var/lib/polarita-openbao/raft/raft/raft.db
    openssl rand 32 > "$tmp/pecet"
    systemd-creds encrypt --name=bao-pecet --with-key=tpm2 --tpm2-pcrs=7 "$tmp/pecet" pecet.cred.next
    mv pecet.cred.next pecet.cred
fi
systemd-creds decrypt --name=bao-pecet pecet.cred "$tmp/otevreno"
[[ $(stat -c %s "$tmp/otevreno") == 32 ]]
if [[ ! -s pecet.cms ]]; then
    openssl cms -encrypt -binary -aes-256-gcm -outform DER -recip "$work/test-obnova.crt" \
        -keyopt rsa_padding_mode:oaep -keyopt rsa_oaep_md:sha256 -in "$tmp/otevreno" -out pecet.cms.next
    mv pecet.cms.next pecet.cms
fi
pub=/srv/polarita/infra/obnova-public.asc
if [[ -s $pub && ! -s pecet.gpg ]]; then
    fpr=$(gpg --homedir "$tmp" --batch --show-keys --with-colons "$pub" 2>/dev/null | awk -F: '$1=="fpr" && !found {print $10;found=1}')
    [[ "$fpr" == 51E76E15F614E0D2A3E7A778247355F84AC671EE ]]
    gpg --homedir "$tmp" --batch --no-autostart --trust-model always --recipient-file "$pub" --output pecet.gpg.next --encrypt "$tmp/otevreno"
    mv pecet.gpg.next pecet.gpg
fi
