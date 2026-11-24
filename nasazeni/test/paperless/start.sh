#!/bin/bash
set -euo pipefail
# Připojení databáze a identity dokončí instalační krok po ověření OCR.
trap 'exit 0' INT TERM PWR
until [[ -x /etc/polarita-paperless/web.sh && -s /run/secrets/pg-paperless && -s /run/secrets/paperless-secret && -s /run/secrets/paperless-oidc_secret ]]; do
    sleep 2 & wait
done
exec /etc/polarita-paperless/web.sh
