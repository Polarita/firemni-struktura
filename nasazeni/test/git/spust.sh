#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
inside=(incus exec -T gitea-test --)
"${inside[@]}" test -s /run/secrets/pg-gitea
"${inside[@]}" test -s /run/secrets/gitea-stroj
"${inside[@]}" systemctl enable --now gitea-test.service
for i in {1..120}; do
    if curl --noproxy '*' --silent --fail --max-time 3 http://10.239.32.13:3000/api/healthz >/dev/null; then break; fi
    sleep 2
done
curl --noproxy '*' --fail --silent --show-error --max-time 5 http://10.239.32.13:3000/api/healthz | python3 -c '
import json,sys
result=json.load(sys.stdin)
assert result["status"] in ("pass","ok"), "Gitea není připravená"
'
db=(incus exec -T postgres-test -- runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 -d gitea)
tables=$("${db[@]}" -c "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public' AND tableowner='gitea' AND tablename IN ('repository','user','version','action_runner')")
[[ $tables == 4 ]]
mode=$("${inside[@]}" stat -c '%a %U' /run/polarita-gitea/app.ini)
[[ $mode == '400 gitea-test' ]]
echo 'Gitea odpověděla na zdravotní zkoušku a vlastní čtyři ověřené tabulky ve vyhrazené databázi PostgreSQL.'
