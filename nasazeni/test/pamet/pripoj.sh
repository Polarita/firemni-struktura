#!/bin/sh
set -eu
test "$(hostname -s)" = polarita-hq
dataset=polarita_zfs/data/bootstrap-test
target=/srv/polarita/data/bootstrap-test
test "$(zfs get -H -o value mountpoint "$dataset")" = "$target"
test "$(zfs get -H -o value encryptionroot "$dataset")" = polarita_zfs
test "$(zfs get -H -o value keystatus "$dataset")" = available
if test "$(zfs get -H -o value mounted "$dataset")" = no; then zfs mount "$dataset"; fi
test "$(findmnt -n -o SOURCE --mountpoint "$target")" = "$dataset"
