#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
work=/srv/polarita/infra/gitea-test
install -d -m 0755 "$work/bin"
exec 9>"$work/.zdroje"
flock 9
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
cd "$tmp"
key=7C9E68152594688862D62AF62D9AE806EC1592E2
gitea=gitea-28.4.0-linux-amd64
runner=gitea-runner-6.0.1-linux-amd64
gsha=154e775bd6bb589fc14cd93a689d8fbc64090aaa3ec537f0e3af298b13c6d386
rsha=37be79b1e72e31e3e02004ee1d768a0bc23224b9520351f46bb7157de7433fbd
if ! echo "$gsha  $work/bin/$gitea" | sha256sum --check --status 2>/dev/null; then
    curl -fsSL --retry 2 --max-time 30 "https://keys.openpgp.org/vks/v1/by-fingerprint/$key" -o vendor.asc
    mkdir -m 0700 pgp
    gpg --homedir "$tmp/pgp" --batch --dearmor -o overeni.gpg vendor.asc
    test "$(gpg --homedir "$tmp/pgp" --batch --with-colons --show-keys vendor.asc | awk -F: '$1=="fpr"{print $10;exit}')" = "$key"
    curl -fsSL --retry 2 --max-time 180 "https://dl.gitea.com/gitea/28.4.0/$gitea" -o "$gitea"
    curl -fsSL --retry 2 --max-time 30 "https://dl.gitea.com/gitea/28.4.0/$gitea.asc" -o "$gitea.asc"
    echo "$gsha  $gitea" | sha256sum -c
    gpgv --homedir "$tmp/pgp" --keyring "$tmp/overeni.gpg" "$gitea.asc" "$gitea"
    install -m 0755 "$gitea" "$work/bin/"
fi
if ! echo "$rsha  $work/bin/$runner" | sha256sum --check --status 2>/dev/null; then
    curl -fsSL --retry 2 --max-time 120 "https://dl.gitea.com/gitea-runner/6.0.1/$runner" -o "$runner"
    echo "$rsha  $runner" | sha256sum -c
    install -m 0755 "$runner" "$work/bin/"
fi
"$work/bin/$gitea" --version
"$work/bin/$runner" --version
