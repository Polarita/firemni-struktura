#!/bin/bash
# Runner pro syntaktickou kontrolu Go potřebuje pouze samostatný program gofmt.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
name=gitea-runner-test
[[ $(incus config get "$name" user.polarita.role) == "$name" ]]
inside=(incus exec -T "$name" --)
sum=fa7bf4ae3c843035ba39608bf37812e2add396822f1a1151cb847db7e867ce97
path=/usr/local/bin/gofmt
if printf '%s  %s\n' "$sum" "$path" | "${inside[@]}" sha256sum --check --status -; then exit 0; fi
work=$(mktemp -d /var/tmp/polarita-gofmt-XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
cd "$work"
apt-get download golang-1.26-go=1.26.8-1~ubuntu0.26.04.2
deb=golang-1.26-go_1.26.8-1~ubuntu0.26.04.2_amd64.deb
echo "a25f64a8b1bd65d68b7ec9497b649f8ed7fb4fddcdfc62d4aea31d9540e110d0  $deb" | sha256sum --check --status
dpkg-deb --fsys-tarfile "$deb" | tar -xOf - ./usr/lib/go-1.26/bin/gofmt >gofmt
echo "$sum  gofmt" | sha256sum --check --status
incus file push --mode=0755 gofmt "$name$path.next"
printf '%s  %s\n' "$sum" "$path.next" | "${inside[@]}" sha256sum --check --status -
"${inside[@]}" mv -T "$path.next" "$path"
