#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == postgres-test && $# == 15 ]]
umask 077
pool=/var/lib/polarita-postgres/pool
install -d -m 0750 -o root -g polarita-pool "$pool"
tmp=$(mktemp -d "$pool/.nastaveni-XXXXXXXX")
trap 'rm -rf "$tmp"' EXIT
echo '[databases]' > "$tmp/pgbouncer.ini"
for route in "$@"; do
    [[ $route =~ ^([a-z][a-z0-9_]+)=(session|transaction)$ ]]
    name=${BASH_REMATCH[1]}
    mode=${BASH_REMATCH[2]}
    echo "$name = host=127.0.0.1 port=5432 dbname=$name pool_mode=$mode" >>"$tmp/pgbouncer.ini"
    runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -c "SELECT format('%s%s%s %s%s%s', chr(34), rolname, chr(34), chr(34), rolpassword, chr(34)) FROM pg_authid WHERE rolname='$name' AND rolpassword LIKE 'SCRAM-SHA-256%'" >>"$tmp/users"
done
[[ $(wc -l <"$tmp/users") == 15 ]]
cat >> "$tmp/pgbouncer.ini" <<'CONF'
[pgbouncer]
listen_addr = 127.0.0.1,10.239.33.12
listen_port = 6432
unix_socket_dir =
auth_type = scram-sha-256
auth_file = /var/lib/polarita-postgres/pool/users
client_tls_sslmode = require
client_tls_protocols = tlsv1.3
client_tls_key_file = /var/lib/polarita-postgres/pki/server.key
client_tls_cert_file = /var/lib/polarita-postgres/pki/server.crt
server_tls_sslmode = verify-full
server_tls_protocols = tlsv1.3
server_tls_ca_file = /var/lib/polarita-postgres/pki/server.crt
default_pool_size = 3
max_db_connections = 6
max_client_conn = 64
log_connections = 0
log_disconnections = 0
CONF
for f in users pgbouncer.ini; do
    chown root:polarita-pool "$tmp/$f"
    chmod 0640 "$tmp/$f"
    mv -f "$tmp/$f" "$pool/$f"
done
cat >/etc/systemd/system/polarita-pgbouncer.service <<'UNIT'
[Unit]
Description=PgBouncer databází Polarita TEST
After=polarita-postgres.service
Requires=polarita-postgres.service
[Service]
User=polarita-pool
Group=polarita-pool
ExecStart=/usr/sbin/pgbouncer /var/lib/polarita-postgres/pool/pgbouncer.ini
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
UMask=0077
NoNewPrivileges=yes
LimitCORE=0
[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/polarita-pgbouncer.service
systemctl daemon-reload
systemctl enable polarita-pgbouncer.service
if systemctl is-active --quiet polarita-pgbouncer.service; then
    systemctl reload polarita-pgbouncer.service
else
    systemctl start polarita-pgbouncer.service
fi
for i in {1..30}; do
    if pg_isready -h 127.0.0.1 -p 6432 -d db_eshop -U db_eshop >/dev/null; then exit 0; fi
    sleep 1
done
exit 1
