#!/bin/bash
# Soukromá část testovací obnovy patří správě hypervizoru na Ejpovicích.
set -euo pipefail
[[ $(hostname -s) == ejpovice && $(id -u) == 0 ]]
umask 077
dir=/etc/polarita-test-obnova
install -d -m 0700 "$dir"
cd "$dir"
exec 9>.lock
flock 9
if [[ ! -s test.key ]]; then
    [[ ! -e test.crt ]]
    openssl genpkey -quiet -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out test.key.next
    mv test.key.next test.key
fi
if [[ ! -s test.crt ]]; then
    openssl req -x509 -new -sha256 -days 3650 -key test.key -out test.crt.next \
        -subj /CN=Polarita-TEST-obnova -addext keyUsage=keyEncipherment
    mv test.crt.next test.crt
fi
if [[ ${1:-} == --pouze-prijemce ]]; then exit 0; fi
guest=(incus exec -T --project polarita polarita-hq --)
work=/srv/polarita/infra/openbao-test
"${guest[@]}" install -d -m 0750 "$work"
# Odlišný certifikát nesmí tiše změnit příjemce existujících záloh.
if "${guest[@]}" test -e "$work/test-obnova.crt"; then
    "${guest[@]}" cat "$work/test-obnova.crt" | cmp - test.crt
else
    incus file push --project polarita --mode=0644 test.crt "polarita-hq$work/test-obnova.crt"
fi
