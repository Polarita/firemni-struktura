#!/bin/bash
# Vstup instalační ai na Ejpovicích pro vydaný TEST.
set -euo pipefail
[[ $(hostname -s) == ejpovice ]]
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
tag=$(python3 -c 'import json; print(json.load(open("nastroje/kanon.json"))["release_tag"])')
commit=$(git rev-parse HEAD)
[[ $(git rev-list -n 1 "$tag") == "$commit" ]]
git diff --quiet HEAD -- nasazeni/test
sudo -n install -d -m 0755 /run/polarita-instalace-test
exec flock --close --nonblock --conflict-exit-code 75 /run/polarita-instalace-test bash -ec '
    for pokus in 1 2 3; do
        [[ $(git rev-parse HEAD) == "$1" ]]
        git diff --quiet HEAD -- nasazeni/test
        if bash nasazeni/test/kroky.sh "$1"; then exit 0; else chyba=$?; fi
        if (( pokus == 3 )); then exit "$chyba"; fi
        printf "Instalace skončila kódem %s, po 30 sekundách ověřím stav a navážu.\n" "$chyba" >&2
        sleep 30
    done
' instalace "$commit"
