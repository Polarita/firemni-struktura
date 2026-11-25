#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 && $(uname -m) == x86_64 ]]
dir=/srv/polarita/infra/medusa-test/distribuce
src=node-v26.13.1-linux-x64
sum=5c063e46bab0fbc1c17cc445d7ff129cbdcd0471be6ed83b6ab864f8143bc864
install -dm0755 "$dir"
exec 9>/run/polarita-medusa-node.lock
flock 9
if [[ ! -e $dir/$src ]]; then
    tmp=$(mktemp -d "$dir/.node-XXXXXXXX")
    trap 'rm -rf -- "$tmp"' EXIT
    curl -fsSL --proto '=https' --retry 3 --connect-timeout 15 --max-time 300 "https://nodejs.org/dist/v26.13.1/$src.tar.xz" -o "$tmp/node.tar.xz"
    printf '%s  %s\n' "$sum" "$tmp/node.tar.xz" | sha256sum -c --status
    tar --no-same-owner -xJf "$tmp/node.tar.xz" -C "$tmp"
    mv -T "$tmp/$src" "$dir/$src"
fi
[[ $("$dir/$src/bin/node" --version) == v26.13.1 ]]
printf 'Node.js 26.13.1 LTS pro Medusu je připraven uvnitř polarita-hq.\n'
