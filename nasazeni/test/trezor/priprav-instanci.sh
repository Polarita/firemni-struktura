#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == openbao-test ]]
getent passwd openbao >/dev/null || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin openbao
dir=/var/lib/polarita-openbao
mountpoint -q "$dir"
install -d -m 0750 -o root -g openbao "$dir"
install -d -m 0700 -o openbao -g openbao "$dir/raft" "$dir/audit"
install -d -m 0750 -o root -g openbao "$dir/tls"
umask 077
cd "$dir/tls"
if [[ ! -s server.key ]]; then
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out server.key.next
    mv server.key.next server.key
fi
if ! openssl x509 -checkend 2592000 -noout -in server.crt >/dev/null 2>&1; then
    openssl req -new -x509 -sha256 -days 365 -key server.key -out server.crt.next \
        -subj /CN=openbao.polarita.test -addext subjectAltName=DNS:openbao.polarita.test,IP:10.239.33.10,IP:127.0.0.1
    mv server.crt.next server.crt
fi
chown root:openbao server.key
chmod 0640 server.key
chmod 0644 server.crt
systemctl daemon-reload
