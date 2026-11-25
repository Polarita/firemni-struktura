#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
lib=$(bash "$src/../inzenyring/rozpocet/nastroje.sh" /var/cache/polarita-rozpocet-test)
schema=$(bash "$src/schema.sh" /var/cache/polarita-distribuce/isdoc)
if ! command -v java >/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 -y --no-install-recommends install openjdk-21-jre-headless=21.0.13.1+2-1~26.04.1 >&2
fi
peppol=$(bash "$src/peppol/pravidla.sh" /var/cache/polarita-distribuce/peppol)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$lib" python3 "$src/publikace.py" "$schema" /srv/polarita/workspace/finance-test/davky "$peppol"
