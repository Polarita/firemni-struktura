#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-akademie-cache.lock
flock 8
vm=akademie-test
conf=/etc/polarita-akademie
incus file push --mode=0644 "$src/cache.php" "$vm$conf/.cache.next"
incus exec -T "$vm" -- mv -T "$conf/.cache.next" "$conf/cache.php"
php=(incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 "$conf/cache.php")
"${php[@]}" --nastav
"${php[@]}"
