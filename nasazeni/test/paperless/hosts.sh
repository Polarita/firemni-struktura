#!/bin/bash
# Připraví tabulku i při samostatné aktualizaci starší instance Paperless.
set -euo pipefail
host=${1:?}
[[ $host =~ ^[a-z0-9.-]+\.ts\.net$ ]]
file=${2:?}/hosts
tmp=$(mktemp "$file.XXXXXXXX")
trap 'rm -f -- "$tmp"' EXIT
printf '127.0.0.1 localhost\n127.0.1.1 paperless-test\n::1 localhost ip6-localhost ip6-loopback\n10.239.32.13 %s\n' "$host" >"$tmp"
if ! cmp -s "$tmp" "$file"; then
    chmod 0644 "$tmp"
    mv -T "$tmp" "$file"
fi
