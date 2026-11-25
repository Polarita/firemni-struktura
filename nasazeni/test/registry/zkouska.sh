#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
run=(incus exec -T postgres-test --)
dst=$("${run[@]}" mktemp -d)
trap '"${run[@]}" rm -rf -- "$dst"' EXIT
tar -C "$src" -cf - zkouska.py vzory.json -C "$src/../inzenyring/revize" spisy_rz.py | "${run[@]}" tar -xf - -C "$dst"
"${run[@]}" python3 -Es "$dst/zkouska.py"
