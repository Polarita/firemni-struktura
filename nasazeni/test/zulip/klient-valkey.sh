#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-test
install -d -m 0755 "$work/conf"
tmp=$(mktemp -d "$work/.klient-XXXXXXXX")
trap 'rm -r -- "$tmp"' EXIT
tar -xOf "$work/zdroje/zulip-server-13.3.tar.gz" zulip-server-13.3/zerver/lib/redis_utils.py >"$tmp/original.py"
printf '96183681492a8c5295fcc6588c47c4ecaaec478c12ca6f135677e2b9761a7203  %s\n' "$tmp/original.py" | sha256sum -c
patch --quiet --batch --fuzz=0 -o "$tmp/redis_utils.py" "$tmp/original.py" "$src/redis-13.3.patch"
python3 -m py_compile "$tmp/redis_utils.py"
incus file pull valkey-test/run/secrets/valkey-cert "$tmp/valkey.crt"
openssl verify -CAfile "$tmp/valkey.crt" -verify_ip 10.239.33.13 "$tmp/valkey.crt"
install -m 0644 "$tmp/valkey.crt" "$tmp/redis_utils.py" "$work/conf/"
