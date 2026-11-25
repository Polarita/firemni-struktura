#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-test-zatez.lock
flock 8
vm=akademie-test
incus file push --mode=0644 "$src/kurz.php" "$vm/etc/polarita-akademie/.kurz.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.kurz.next /etc/polarita-akademie/kurz.php
incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/kurz.php
