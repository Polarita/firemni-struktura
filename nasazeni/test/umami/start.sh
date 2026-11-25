#!/bin/sh
set -eu
cd /app
while ! test -s /run/secrets/umami-two_factor || ! test -s /run/secrets/pg-umami || ! test -s /run/secrets/umami-secret; do sleep 5; done
# Agent vydává heslo PostgreSQL v URL-safe abecedě. Soukromé údaje zůstanou v paměti procesu.
export APP_SECRET="$(cat /run/secrets/umami-secret)"
export TWO_FACTOR_ENCRYPTION_KEY="$(cat /run/secrets/umami-two_factor)"
export NODE_EXTRA_CA_CERTS=/etc/polarita-umami/postgres.crt
export DATABASE_URL="postgresql://umami:$(cat /run/secrets/pg-umami)@postgres.polarita.test:5432/umami?sslmode=verify-full&sslrootcert=/etc/polarita-umami/postgres.crt"
export DISABLE_BOT_CHECK=1 DISABLE_TELEMETRY=1 DISABLE_UPDATES=1 NEXT_TELEMETRY_DISABLED=1
export PATH="/app/node_modules/.bin:$PATH"
node scripts/check-db.js
node scripts/update-tracker.js
export HOSTNAME=127.0.0.1 PORT=3000
exec node server.js
