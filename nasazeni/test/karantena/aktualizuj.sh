#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
vm=clamav-signatury-test
# Opakování a čas do dalšího pokusu řídí freshclam podle odpovědi distributora.
incus exec -T "$vm" -- freshclam --config-file=/etc/clamav/polarita-freshclam.conf --stdout
incus exec -T "$vm" -- sh -ec '
cd /data/polarita-db
for name in main daily bytecode; do
    file=$name.cld
    test -s "$file" || file=$name.cvd
    sigtool --info "$file"
done'
