#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == postgres-test ]]
data=/var/lib/polarita-postgres
mountpoint -q "$data"
getent group polarita-db-tls >/dev/null || groupadd --system polarita-db-tls
id polarita-pool >/dev/null 2>&1 || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin polarita-pool
usermod -aG polarita-db-tls postgres
usermod -aG polarita-db-tls polarita-pool
install -d -m 0711 -o root -g root "$data"
install -d -m 0700 -o postgres -g postgres "$data/db"
install -d -m 0750 -o root -g polarita-db-tls "$data/pki"
install -d -m 0755 /etc/polarita-postgres
umask 077
if [[ ! -s $data/pki/server.key ]]; then
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$data/pki/server.key.next"
    mv "$data/pki/server.key.next" "$data/pki/server.key"
fi
if ! openssl x509 -checkend 2592000 -noout -in "$data/pki/server.crt" >/dev/null 2>&1; then
    openssl req -new -x509 -key "$data/pki/server.key" -sha256 -days 365 -subj /CN=postgres.polarita.test         -addext subjectAltName=DNS:postgres.polarita.test,IP:10.239.33.12,IP:127.0.0.1 -out "$data/pki/server.crt.next"
    mv "$data/pki/server.crt.next" "$data/pki/server.crt"
fi
chown root:polarita-db-tls "$data/pki/server.key"
chmod 0640 "$data/pki/server.key"
chmod 0644 "$data/pki/server.crt"
if [[ ! -s $data/db/PG_VERSION ]]; then
    [[ -z $(ls -A "$data/db") ]]
    runuser -u postgres -- /usr/lib/postgresql/18/bin/initdb -D "$data/db"         --locale=C.UTF-8 --encoding=UTF8 --auth-local=peer --auth-host=scram-sha-256 --data-checksums
fi
[[ $(cat "$data/db/PG_VERSION") == 18 ]]
cat >/etc/polarita-postgres/postgresql.conf <<'CONF'
data_directory = '/var/lib/polarita-postgres/db'
hba_file = '/etc/polarita-postgres/pg_hba.conf'
listen_addresses = '127.0.0.1,10.239.33.12'
unix_socket_directories = '/run/postgresql'
ssl = on
ssl_cert_file = '/var/lib/polarita-postgres/pki/server.crt'
ssl_key_file = '/var/lib/polarita-postgres/pki/server.key'
ssl_min_protocol_version = 'TLSv1.3'
password_encryption = 'scram-sha-256'
max_connections = 48
shared_buffers = '32MB'
work_mem = '1MB'
maintenance_work_mem = '16MB'
max_wal_size = '256MB'
max_parallel_workers = 1
timezone = 'UTC'
include_if_exists = '/etc/polarita-postgres/archivace.conf'
log_statement = 'none'
log_min_error_statement = 'panic'
CONF
cat >/etc/polarita-postgres/pg_hba.conf <<'CONF'
local all postgres peer
local db_erp_lhutnik pol_metadata_api peer
local db_erp_lhutnik pol_metadata_read peer
local db_erp_lhutnik pol_prijem_sanonu peer
local db_paperclip pol_decisions_bridge peer
local all all scram-sha-256
host all postgres 0.0.0.0/0 reject
host all postgres ::/0 reject
hostssl sameuser all 10.239.33.1/32 scram-sha-256
hostssl keycloak keycloak 10.239.32.11/32 scram-sha-256
hostssl gitea gitea 10.239.32.13/32 scram-sha-256
hostssl db_paperclip db_paperclip 10.239.32.18/32 scram-sha-256
hostssl paperless paperless 10.239.32.21/32 scram-sha-256
hostssl db_akademie db_akademie 10.239.32.24/32 scram-sha-256
hostssl db_eshop db_eshop 10.239.32.23/32 scram-sha-256
hostssl umami umami 10.239.32.22/32 scram-sha-256
hostssl vikunja vikunja 10.239.32.20/32 scram-sha-256
hostssl zulip zulip 10.239.32.16/32 scram-sha-256
hostssl sameuser all 127.0.0.1/32 scram-sha-256
CONF
chmod 0644 /etc/polarita-postgres/*.conf
cat >/etc/systemd/system/polarita-postgres.service <<'UNIT'
[Unit]
Description=PostgreSQL Polarita TEST
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/var/lib/polarita-postgres
[Service]
Type=notify
User=postgres
Group=postgres
# Kromě klientských procesů potřebuje PostgreSQL místo pro WAL a autovacuum.
TasksMax=96
RuntimeDirectory=postgresql
RuntimeDirectoryMode=0755
ExecStart=/usr/lib/postgresql/18/bin/postgres -D /var/lib/polarita-postgres/db -c config_file=/etc/polarita-postgres/postgresql.conf
ExecReload=/bin/kill -HUP $MAINPID
KillSignal=SIGINT
TimeoutStopSec=120
Restart=on-failure
UMask=0077
LimitCORE=0
MemorySwapMax=0
[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/polarita-postgres.service
systemctl daemon-reload
systemctl enable --now polarita-postgres.service
systemctl reload polarita-postgres.service
runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 -c "select current_setting('server_version'),current_setting('ssl'),current_setting('password_encryption'),current_setting('data_checksums')"
