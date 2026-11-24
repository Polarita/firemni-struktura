#!/bin/bash
# Stalwart 1.2 ukládá QueueClass::Message do samostatné rodiny e s osmibajtovým klíčem.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
db=/var/lib/incus/storage-pools/default/custom/default_stalwart-mx-test-data/rocksdb
[[ -s $db/CURRENT ]]
# RocksDB otevře pouze sekundární pohled. Primární svazek je v této jmenné oblasti pouze ke čtení.
systemd-run --quiet --pipe --wait --collect -p PrivateNetwork=yes -p ProtectSystem=strict -p PrivateTmp=yes \
    -p "ReadOnlyPaths=$db" /bin/bash -ec '
        set -euo pipefail
        t=$(mktemp -d)
        exec java -XX:+UseSerialGC -Xms8m -Xmx48m -cp "/opt/polarita-rocksdb/*:/opt/polarita-rocksdb" RocksSonda fronta "$1" "$t/cache"
    ' fronta "$db"
