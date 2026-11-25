#!/bin/bash
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
root=$1
install -d "$root"
exec 9>"$root/.priprava"
flock 9
key=$(sha256sum "$src/kola.lock" | cut -d' ' -f1)
export PYTHONPATH="$src/../../cad"
python3 -c 'from pathlib import Path; from kola import prepare; import sys; prepare(Path(sys.argv[1]),Path(sys.argv[2]))' "$root/kola" "$src/kola.lock"
if [[ ! -d $root/$key ]]; then
    tmp=$(mktemp -d "$root/.xz-XXXXXXXX")
    trap 'rm -r -- "$tmp"' EXIT
    while IFS= read -r line; do
        name=${line##*/}; file=${name%#*}; sum=${line##*#sha256=}
        printf '%s/%s --hash=sha256:%s\n' "$root/kola" "$file" "$sum"
    done <"$src/kola.lock" >"$tmp/pozadavky"
    pip=("$root"/kola/pip-*.whl)
    PYTHONPATH="${pip[0]}" python3 -m pip --isolated --disable-pip-version-check install --no-index --no-deps \
        --no-cache-dir --no-compile --require-hashes --target "$tmp/lib" -r "$tmp/pozadavky" >&2
    chmod 0755 "$tmp/lib"
    mv -T "$tmp/lib" "$root/$key"
fi
schema="$root/NZ-43151f01.xsd"
sha=43151f01c79707fc02e62fc2f02ff4bd7e73b407886777706b25d2fdfe664c1d
if ! [[ -f $schema ]] || ! echo "$sha  $schema" | sha256sum --status -c; then
    curl -fsSL --proto '=https' --proto-redir '=https' --retry 3 --max-time 90 https://www.xc4.cz/download/NZ.xsd -o "$schema.next"
    echo "$sha  $schema.next" | sha256sum --status -c
    chmod 0644 "$schema.next"
    mv -T "$schema.next" "$schema"
fi
printf '%s\n' "$root/$key"
