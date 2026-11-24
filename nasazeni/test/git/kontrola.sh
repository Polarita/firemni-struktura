#!/bin/bash
# V malé VM soutěží prohlížeč v CI a offline kontrola příloh o stejnou paměť.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
dest=${1:?Chybí adresář připnuté revize}
exec 8>/run/polarita-test-zatez.lock
flock 8
python3 "$src/zdroj_ci.py" "$dest/zdroj-ci.tar.gz"
bash "$src/sken.sh" >&2
python3 "$src/zdroj_ci.py" "$dest/zdroj-ci.tar.gz" --zkouska-skenu
python3 "$src/repozitar.py" --ochrana --kandidat "$dest/revize-ci.json"
python3 "$src/over_ci.py" "$dest/revize-ci.json"
