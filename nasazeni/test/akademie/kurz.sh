#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-test-zatez.lock
flock 8
vm=akademie-test
incus exec -T "$vm" -- install -dm0700 -o 33 -g 33 /var/lib/polarita-vzory
incus file push --mode=0644 "$src/osvedceni.php" "$vm/etc/polarita-akademie/.osvedceni.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.osvedceni.next /etc/polarita-akademie/osvedceni.php
incus file push --mode=0644 "$src/kurz.php" "$vm/etc/polarita-akademie/.kurz.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.kurz.next /etc/polarita-akademie/kurz.php
incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/kurz.php
proof=/srv/polarita/workspace/dukazy/blok-09
install -dm0750 "$proof"
pdf=$(mktemp -p "$proof" .osvedceni-XXXXXXXX)
trap 'unlink "$pdf" 2>/dev/null || true' EXIT
incus exec -T "$vm" -- cat /var/lib/polarita-vzory/osvedceni.pdf >"$pdf"
content=$(incus exec -T paperless-test -- pdftotext -enc UTF-8 - - <"$pdf")
for label in 'VZOR TEST' 'Cvičné osvědčení Akademie' 'vyplnění odpovědního listu' 'Účastník' 'TEST A'; do
    [[ $content == *"$label"* ]] || { echo "Náhled neobsahuje text: $label" >&2; exit 1; }
done
mv -T "$pdf" "$proof/akademie-osvedceni-vzor.pdf"
echo 'V tištěném náhledu Custom Certificate je označení VZOR TEST, název kurzu a jméno fiktivního účastníka.'
