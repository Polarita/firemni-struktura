#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
vm=postgres-test
run=(incus exec -T "$vm" --)
[[ $(incus config get "$vm" user.polarita.role) == "$vm" ]]
dst=/opt/polarita-inzenyring-test
"${run[@]}" install -dm0755 "$dst"
rev=$(cd "$src" && sha256sum registr.py vzor/{metodika,doklady,trasa}.json | sha256sum | cut -d' ' -f1)
"${run[@]}" install -dm0755 "$dst/$rev"
tar -C "$src" -cf - registr.py vzor/metodika.json vzor/doklady.json vzor/trasa.json | "${run[@]}" tar xf - -C "$dst/$rev"
spis=$(cd "$src" && python3 -c 'from prijem import CASE; print(CASE)')
"${run[@]}" python3 "$dst/$rev/registr.py" "$dst/$rev/vzor" "$spis"
