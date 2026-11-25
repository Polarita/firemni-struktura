#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
lib=$(bash "$src/../inzenyring/rozpocet/nastroje.sh" /var/cache/polarita-rozpocet-test)
schema=$(bash "$src/schema.sh" /var/cache/polarita-distribuce/isdoc)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$lib" python3 "$src/publikace.py" "$schema" /srv/polarita/workspace/finance-test/davky
