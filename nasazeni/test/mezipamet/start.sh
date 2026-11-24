#!/bin/sh
set -eu
for f in valkey-cert valkey-klic valkey-acl; do
    while test ! -s "/run/secrets/$f"; do sleep 2; done
done
exec docker-entrypoint.sh valkey-server /etc/polarita-valkey/valkey.conf
