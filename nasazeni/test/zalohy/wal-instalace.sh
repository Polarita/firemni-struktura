#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
bash "$src/../incus/balicky.sh" postgres-test pgbackrest=2.58.0-1
incus exec -T postgres-test -- bash -se <"$src/wal-nastav.sh"
