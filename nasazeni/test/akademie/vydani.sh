#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-akademie-vydani.lock
flock 8
vm=akademie-test
php=(incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/vydani.php)
incus file push --mode=0644 "$src/vydani.php" "$vm/etc/polarita-akademie/.vydani.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.vydani.next /etc/polarita-akademie/vydani.php
incus file push --mode=0644 "$src/cti_qr.py" paperless-test/usr/local/share/.polarita-qr.next
incus exec -T paperless-test -- mv -T /usr/local/share/.polarita-qr.next /usr/local/share/polarita-qr.py
proof=/srv/polarita/workspace/dukazy/blok-09
install -dm0750 "$proof"
pdf=$(mktemp -p "$proof" .osvedceni-XXXXXXXX)
trap 'unlink "$pdf" 2>/dev/null || true' EXIT
"${php[@]}" pdf >"$pdf"
incus exec -T paperless-test -- python3 /usr/local/share/polarita-qr.py <"$pdf" | "${php[@]}" over
mv -T "$pdf" "$proof/akademie-osvedceni-vydane.pdf"
