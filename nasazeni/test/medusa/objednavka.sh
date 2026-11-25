#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 9>/run/polarita-medusa-objednavka.lock
flock 9
inside=(incus exec -T medusa-test --)
"${inside[@]}" install -dm0700 /var/lib/polarita-medusa-test /etc/polarita-medusa/prejimka
for f in katalog.py objednavka.py prihlaseni.py; do
    incus file push --mode=0644 "$src/$f" "medusa-test/etc/polarita-medusa/prejimka/.$f-next"
    "${inside[@]}" mv -T "/etc/polarita-medusa/prejimka/.$f-next" "/etc/polarita-medusa/prejimka/$f"
done
"${inside[@]}" python3 /etc/polarita-medusa/prejimka/prihlaseni.py 127.0.0.1 --objednavka </srv/polarita/data/bootstrap-test/test-login/heslo
