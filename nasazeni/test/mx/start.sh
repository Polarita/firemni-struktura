#!/bin/sh
# Vstupní bod výhradně pro samostatný testovací MX.
set -eu
umask 077
conf=/etc/polarita-mx
data=/var/lib/stalwart
# Novému svazku při prvním nasazení nastaví vlastnictví instalátor přes Incus.
attempt=0
while [ ! -w "$data" ]; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 180 ]
    sleep 1
done
mkdir -p "$data/tls" "$data/log"
if [ ! -s "$data/tls/mx.key" ]; then
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$data/tls/mx.key.next"
    mv "$data/tls/mx.key.next" "$data/tls/mx.key"
fi
if ! openssl x509 -checkend 604800 -noout -in "$data/tls/mx.crt" >/dev/null 2>&1; then
    openssl req -x509 -new -days 90 -key "$data/tls/mx.key" -subj /CN=mx.polarita.test \
        -addext subjectAltName=DNS:mx.polarita.test -out "$data/tls/mx.crt.next"
    mv "$data/tls/mx.crt.next" "$data/tls/mx.crt"
fi
# Přechodné heslo zná jen tento proces a lokální správní klient.
password=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
export STALWART_RECOVERY_MODE_BIND=127.0.0.1
export STALWART_HOSTNAME=mx.polarita.test
STALWART_RECOVERY_MODE=1 STALWART_RECOVERY_ADMIN="admin:$password" \
    stalwart --config "$conf/config.json" >"$data/konfigurace.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" || true' EXIT
attempt=0
until curl --max-time 1 -fsS http://127.0.0.1:8080/healthz/live >/dev/null 2>&1; do
    kill -0 "$pid"
    attempt=$((attempt + 1))
    [ "$attempt" -lt 60 ]
    sleep 1
done
(
    export XDG_CACHE_HOME="$data/cli" XDG_DATA_HOME="$data/cli"
    export STALWART_URL=http://127.0.0.1:8080 STALWART_USER=admin STALWART_PASSWORD="$password"
    "$conf/stalwart-cli" apply --file "$conf/plan.ndjson"
    "$conf/stalwart-cli" query Domain --fields id --json >"$data/domeny.ndjson"
    [ ! -s "$data/domeny.ndjson" ]
) >"$data/plan.log" 2>&1
kill "$pid"
wait "$pid" || true
trap - EXIT
unset password
exec stalwart --config "$conf/config.json"
