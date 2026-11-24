#!/bin/bash
set -euo pipefail
# Připojení databáze a identity dokončí instalační krok po ověření OCR.
until [[ -x /etc/polarita-paperless/web.sh && -s /run/secrets/pg-paperless ]]; do sleep 5; done
exec /etc/polarita-paperless/web.sh
