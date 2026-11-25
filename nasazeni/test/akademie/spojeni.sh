#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
vm=akademie-test
inside=(incus exec -T "$vm" --)
"${inside[@]}" install -dm0755 /etc/polarita-akademie
# Do aplikace putují pouze veřejné certifikáty serverů.
incus exec -T postgres-test -- cat /var/lib/polarita-postgres/pki/server.crt |
    incus file push --mode=0644 - "$vm/etc/polarita-akademie/.postgres.next"
incus exec -T valkey-test -- cat /run/secrets/valkey-cert |
    incus file push --mode=0644 - "$vm/etc/polarita-akademie/.valkey.next"
"${inside[@]}" sh -ec '
    cd /etc/polarita-akademie
    for service in postgres valkey; do
        openssl x509 -noout -checkend 0 -in ".$service.next" >/dev/null
        mv -T ".$service.next" "$service.crt"
    done'
incus file push --mode=0644 "$src/spojeni.php" "$vm/etc/polarita-akademie/spojeni.php"
incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/spojeni.php
