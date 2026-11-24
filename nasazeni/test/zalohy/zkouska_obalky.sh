#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == ejpovice && $EUID == 0 ]]
src=$1
[[ $src =~ ^/srv/polarita/infra/(stavba|releases)/[0-9a-f]{40}/nasazeni/test/zalohy$ ]]
guest=(incus exec -T --project polarita polarita-hq --)
"${guest[@]}" python3 "$src/obnovovaci_pristup.py" --vytvor
"${guest[@]}" incus exec -T restic-test -- cat /var/lib/restic-test/obnova/pristup.cms |
    openssl cms -decrypt -binary -inform DER -recip /etc/polarita-test-obnova/test.crt -inkey /etc/polarita-test-obnova/test.key |
    "${guest[@]}" python3 "$src/obnovovaci_pristup.py" --over
