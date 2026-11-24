#!/bin/sh
set -eu
umask 007
chown valkey:1000 /run/paperless-broker
chmod 2750 /run/paperless-broker
exec docker-entrypoint.sh valkey-server --port 0 \
    --unixsocket /run/paperless-broker/valkey.sock --unixsocketperm 770 \
    --dir /data --appendonly yes --appendfsync everysec --save "" \
    --maxmemory 56mb --maxmemory-policy noeviction
