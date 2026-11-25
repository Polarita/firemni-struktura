#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 && $(uname -m) == x86_64 ]]
vm=reditelstvi-test
[[ $(incus config get "$vm" user.polarita.role) == "$vm" ]]
version=0.15.1
archive=typst-x86_64-unknown-linux-musl
sha=a6d077d0a95eed5a2eba715b2dae06be954f624ccbf85758a03f389ded33118c
cache=/srv/polarita/infra/typst-test
install -d -m0755 "$cache"
exec 7>"$cache/.instalace"
flock 7
if [[ ! -f $cache/$sha.tar.xz ]]; then
    tmp=$(mktemp "$cache/.stahovani-XXXXXXXX")
    trap 'rm -f -- "$tmp"' EXIT
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --retry 3 \
        "https://github.com/typst/typst/releases/download/v$version/$archive.tar.xz" --output "$tmp"
    echo "$sha  $tmp" | sha256sum -c - >/dev/null
    mv -T "$tmp" "$cache/$sha.tar.xz"
fi
echo "$sha  $cache/$sha.tar.xz" | sha256sum -c - >/dev/null
tmp=$(mktemp "$cache/.typst-XXXXXXXX")
trap 'rm -f -- "$tmp"' EXIT
tar -xJOf "$cache/$sha.tar.xz" "$archive/typst" >"$tmp"
expected=$(sha256sum "$tmp" | cut -d' ' -f1)
target=/usr/local/bin/polarita-typst
inside=(incus exec -T "$vm" --)
if [[ $("${inside[@]}" sha256sum "$target" 2>/dev/null | cut -d' ' -f1) != "$expected" ]]; then
    incus file push --mode=0755 "$tmp" "$vm$target.next"
    "${inside[@]}" sh -ec 'echo "$1  $2.next" | sha256sum -c - >/dev/null; mv -f "$2.next" "$2"' typst "$expected" "$target"
fi
"${inside[@]}" "$target" --version | grep -F "typst $version "
