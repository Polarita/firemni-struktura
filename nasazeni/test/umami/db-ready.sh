#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
sql="SELECT EXISTS (SELECT FROM pg_extension WHERE extname='pgcrypto')
           AND has_database_privilege('umami', current_database(), 'CONNECT')
           AND has_schema_privilege('umami', 'public', 'USAGE')
           AND has_schema_privilege('umami', 'public', 'CREATE')"
ok=$(incus exec -T postgres-test -- runuser -u postgres -- psql -XqAtw -v ON_ERROR_STOP=1 -d umami -c "$sql")
[[ $ok == t ]]
touch /srv/polarita/infra/umami-test/conf/databaze-pripravena
