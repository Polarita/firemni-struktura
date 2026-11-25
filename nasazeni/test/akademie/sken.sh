#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-akademie-sken.lock
flock 8
vm=akademie-test
run=(incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/sken.php)
incus file push --mode=0644 "$src/sken.php" "$vm/etc/polarita-akademie/.sken.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.sken.next /etc/polarita-akademie/sken.php
incus file push --mode=0644 "$src/vypln_arch.py" paperless-test/usr/local/share/.polarita-arch.next
incus exec -T paperless-test -- mv -T /usr/local/share/.polarita-arch.next /usr/local/share/polarita-arch.py
declare -A jobs
for group in A B; do
    jobs[$group]=$("${run[@]}" arch "$group" |
        incus exec -T paperless-test -- python3 /usr/local/share/polarita-arch.py "$group" |
        "${run[@]}" odesli "$group")
    [[ ${jobs[$group]} =~ ^[1-9][0-9]*$ ]]
done
for group in A B; do
    for ((i=0; i<60; ++i)); do
        if "${run[@]}" over "$group" <<<"${jobs[$group]}"; then break; else status=$?; fi
        [[ $status == 75 ]] || exit "$status"
        sleep 15
    done
    (( i < 60 )) || { echo "Offline Quiz dosud nedokončil úlohu ${jobs[$group]}." >&2; exit 75; }
done
