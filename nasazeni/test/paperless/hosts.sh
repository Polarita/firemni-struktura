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
# Při průběžné instalaci může archiv dál obsluhovat stávající relace se starým /s6-init.
if [[ ${3:-} == --pripoj ]]; then
    [[ $(incus config get paperless-test user.polarita.role) == paperless-test ]]
    incus exec -T paperless-test -- sh -ec 'cmp -s /etc/polarita-paperless/hosts /etc/hosts || mount --bind /etc/polarita-paperless/hosts /etc/hosts'
    incus exec -T paperless-test --user 1000 --group 1000 -- python3 -c 'import socket,sys
if {r[4][0] for r in socket.getaddrinfo(sys.argv[1],443)} != {"10.239.32.13"}:
    raise RuntimeError("Účet archivu nepřeložil interní adresu Keycloaku.")
print("Účet Paperless překládá název identity na soukromou adresu.")' "$host"
fi
