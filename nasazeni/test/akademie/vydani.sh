#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-akademie-vydani.lock
flock 8
vm=akademie-test
php=(incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/vydani.php)
incus file push --mode=0644 "$src/komise.php" "$vm/etc/polarita-akademie/.komise.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.komise.next /etc/polarita-akademie/komise.php
incus file push --mode=0644 "$src/vydani.php" "$vm/etc/polarita-akademie/.vydani.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.vydani.next /etc/polarita-akademie/vydani.php
incus file push --mode=0644 "$src/cti_qr.py" paperless-test/usr/local/share/.polarita-qr.next
incus exec -T paperless-test -- mv -T /usr/local/share/.polarita-qr.next /usr/local/share/polarita-qr.py
proof=/srv/polarita/workspace/dukazy/blok-09
install -dm0750 "$proof"
# Stejné vydání má i při opakování jediný originál. Generátor PDF přidává čas vykreslení.
metadata=$("${php[@]}" doklad)
[[ $metadata =~ ^(20[0-9]{2})\ ([0-9a-f]{64})$ ]]
year=${BASH_REMATCH[1]}
issued="$proof/akademie-osvedceni-${BASH_REMATCH[2]}.pdf"
tmp=$(mktemp -p "$proof" .osvedceni-XXXXXXXX)
trap 'unlink "$tmp" 2>/dev/null || true' EXIT
if [[ -f $issued ]]; then
    pdf=$issued
else
    "${php[@]}" pdf >"$tmp"
    pdf=$tmp
fi
incus exec -T paperless-test -- python3 /usr/local/share/polarita-qr.py <"$pdf" | "${php[@]}" over
if [[ $pdf == "$tmp" ]]; then mv -T "$tmp" "$issued"; fi
python3 "$src/../archiv/osvedceni.py" "$issued" "$year"
cp -- "$issued" "$tmp"
mv -T "$tmp" "$proof/akademie-osvedceni-vydane.pdf"
