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
        ldb --db="$1" --secondary_path="$t/cache" --column_family=e --ignore_unknown_options scan --no_value --key_hex |
            awk '\''/^0x[0-9A-Fa-f]{16}$/ {n++;next} {bad=1} END {if (bad) exit 1; print n+0}'\''
    ' fronta "$db"
