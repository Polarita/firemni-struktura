#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T checkmk-test --)
site=/omd/sites/polarita
dest=$site/etc/check_mk/conf.d/polarita-hq.mk
incus file push --mode=0644 "$src/polarita-host.mk" "checkmk-test$dest"
"${inside[@]}" chown polarita:polarita "$dest"
as_site=("${inside[@]}" runuser -l polarita -c)
"${as_site[@]}" 'cmk -d polarita-hq | grep -F "Polarita aktualnost sond"'
"${as_site[@]}" 'cmk -I polarita-hq'
"${as_site[@]}" 'cmk -O'
"${as_site[@]}" 'cmk -nv polarita-hq'
