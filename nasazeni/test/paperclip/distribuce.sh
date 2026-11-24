#!/bin/bash
# Načte veřejné artefakty v přesných verzích do instalační cache uvnitř ředitelství.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 && $(uname -m) == x86_64 ]]
cache=/srv/polarita/infra/paperclip-test/distribuce
install -d -m 0755 "$cache"
cd "$cache"
exec 9>.stazeni
flock 9
tmp=$(mktemp -d -p "$cache")
trap 'rm -r -- "$tmp"' EXIT
node=node-v24.22.3-linux-x64
node_hash=4f2b175a6d53a5c617a80dba2676238a0688cef28c6da4eba35c7d844e66fcfb
if [[ ! -f $node.tar.xz ]] || ! printf '%s  %s\n' "$node_hash" "$node.tar.xz" | sha256sum -c --status 2>/dev/null; then
    curl -fsSL --proto '=https' --retry 3 "https://nodejs.org/dist/v24.22.3/$node.tar.xz" -o "$tmp/$node.tar.xz"
    (cd "$tmp"; printf '%s  %s\n' "$node_hash" "$node.tar.xz" | sha256sum -c)
    install -m 0644 "$tmp/$node.tar.xz" "$node.tar.xz.next"
    mv -T "$node.tar.xz.next" "$node.tar.xz"
fi
if [[ ! -d $node ]]; then
    tar -xJf "$node.tar.xz" -C "$tmp" --no-same-owner
    [[ $("$tmp/$node/bin/node" --version) == v24.22.3 ]]
    mv -T "$tmp/$node" "$node"
fi
[[ $("./$node/bin/node" --version) == v24.22.3 ]]
server=server-2026.1117.0.tgz
expected='Aw5uIQjP0E78k1oCPI5B6706MYh20xMkg0nq8i9rMXD8eqbH1gzl2JBQynM/3jL91zx0rr1Csz0TUaLhcnpBjA=='
if [[ ! -f $server || $(openssl dgst -sha512 -binary "$server" | base64 -w0) != "$expected" ]]; then
    curl -fsSL --proto '=https' --retry 3 "https://registry.npmjs.org/@paperclipai/server/-/$server" -o "$tmp/$server"
    [[ $(openssl dgst -sha512 -binary "$tmp/$server" | base64 -w0) == "$expected" ]]
    chmod 0644 "$tmp/$server"
    mv -T "$tmp/$server" "$server"
fi
echo 'Instalační cache obsahuje ověřené vydání Paperclipu 2026.1117.0 a Node.js v24.22.3.'
