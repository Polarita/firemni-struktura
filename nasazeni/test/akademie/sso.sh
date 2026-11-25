#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
host=${1:?Chybí DNS jméno TEST}
[[ $host =~ ^[a-z0-9.-]+[.]ts[.]net$ ]]
exec 8>/run/polarita-akademie-sso.lock
flock 8
subject=$(incus exec -T postgres-test -- runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 -d keycloak <<'SQL'
SELECT u.id FROM user_entity u JOIN realm r ON r.id=u.realm_id
WHERE r.name='polarita' AND u.username='spravce' AND u.email='spravce@polarita.test'
  AND u.enabled AND u.email_verified;
SQL
)
[[ $subject =~ ^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$ ]]
vm=akademie-test
incus file push --mode=0644 "$src/sso.php" "$vm/etc/polarita-akademie/.sso.next"
incus exec -T "$vm" -- mv -T /etc/polarita-akademie/.sso.next /etc/polarita-akademie/sso.php
python3 - <<'PY' | incus exec -T "$vm" --user 33 --group 33 -- php8.4 -d zend.exception_ignore_args=1 /etc/polarita-akademie/sso.php "$host" "$subject"
import ipaddress
import json
# Všechny ostatní adresy ve firemní síti dál pokrývá původní zákaz Moodle.
private = ipaddress.ip_network('10.0.0.0/8')
identity = ipaddress.ip_network('10.239.32.13/32')
print(json.dumps([str(net) for net in private.address_exclude(identity)]))
PY
