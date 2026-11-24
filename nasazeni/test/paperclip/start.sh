#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == paperclip-test && $(id -u) == 17308 ]]
password=$(</run/secrets/pg-db_paperclip)
[[ $password =~ ^[a-zA-Z0-9_-]{32,128}$ ]]
export DATABASE_URL="postgresql://db_paperclip:$password@10.239.33.12:5432/db_paperclip?sslmode=verify-full"
BETTER_AUTH_SECRET=$(</run/secrets/paperclip-auth)
PAPERCLIP_AGENT_JWT_SECRET=$(</run/secrets/paperclip-jwt)
PAPERCLIP_SECRETS_MASTER_KEY=$(</run/secrets/paperclip-master)
[[ $BETTER_AUTH_SECRET =~ ^[a-zA-Z0-9_-]{48,128}$ &&
   $PAPERCLIP_AGENT_JWT_SECRET =~ ^[a-zA-Z0-9_-]{48,128}$ &&
   $PAPERCLIP_SECRETS_MASTER_KEY =~ ^[a-f0-9]{64}$ ]]
export BETTER_AUTH_SECRET PAPERCLIP_AGENT_JWT_SECRET PAPERCLIP_SECRETS_MASTER_KEY
exec /opt/node/bin/node /opt/paperclip/current/node_modules/@paperclipai/server/dist/index.js
