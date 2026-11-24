#!/bin/bash
set -euo pipefail
# Připojení databáze a identity dokončí instalační krok po ověření OCR.
trap 'exit 0' INT TERM PWR
# Incus při studeném startu OCI připojí vlastní /etc/hosts i přes stejnojmenný disk.
if ! cmp -s /etc/polarita-paperless/hosts /etc/hosts; then
    mount --bind /etc/polarita-paperless/hosts /etc/hosts
fi
until [[ -x /etc/polarita-paperless/web.sh && -s /run/secrets/pg-paperless && -s /run/secrets/paperless-secret && -s /run/secrets/paperless-oidc_secret ]]; do
    sleep 2 & wait
done
exec /etc/polarita-paperless/web.sh
