#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == ejpovice && $3 =~ ^[a-f0-9]{40}$ ]]
src=$(cd "$(dirname "$0")" && pwd)
g=(sudo -n incus exec -T --project polarita polarita-hq --)
"${g[@]}" bash "$1/nasazeni/test/ecomail/instalace.sh"
role=(/usr/local/sbin/polarita-ecomail-test)
list="servis-${3:0:12}"
options=(--seznam "$list" --host "$2")
"${g[@]}" "${role[@]}" prvni "${options[@]}"
"${g[@]}" "${role[@]}" zprava "${options[@]}" --kontrola-zakaznika | python3 "$src/over_vpn.py" "$2" nahled
"${g[@]}" "${role[@]}" zprava "${options[@]}" | python3 "$src/over_vpn.py" "$2" odhlasit
"${g[@]}" "${role[@]}" druha "${options[@]}"
"${g[@]}" "${role[@]}" druha "${options[@]}"
"${g[@]}" bash -ec '
    d=/var/lib/polarita-ecomail-test
    install -dm0755 "$d"
    tmp=$(mktemp "$d/.kampane.XXXXXXXX")
    trap '\''rm -f -- "$tmp"'\'' EXIT
    "$@" prehled >"$tmp"
    chmod 0644 "$tmp"
    mv -T "$tmp" "$d/kampane.json"
' -- "${role[@]}"
"${g[@]}" /opt/polarita-ads-mcp-test/current/sdk/bin/python -I "$1/nasazeni/test/ecomail/over_mcp.py" "$list"
