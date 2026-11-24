#!/bin/bash
set -eu
# Vlastní služba nikdy nezavádí vestavěnou databázi. Agent může po startu VM doručit heslo později.
while [[ ! -s /run/secrets/pg-keycloak || ! -f /etc/polarita-id/databaze-pripravena ]]; do sleep 2; done
KC_DB_PASSWORD=$(cat /run/secrets/pg-keycloak)
export KC_DB_PASSWORD
exec /opt/keycloak/bin/kc.sh start --import-realm
