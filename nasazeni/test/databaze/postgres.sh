#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/postgres-test
install -d -m 0750 "$work/tofu"
exec 8>"$work/.instalace"
flock 8
if incus info postgres-test >/dev/null 2>&1; then
    [[ $(incus config get postgres-test user.polarita.role) == postgres-test ]]
else
    bash "$src/obraz.sh"
fi
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita/data/postgres) == polarita_zfs/data/postgres ]]
[[ $(zfs get -Hp -o value recordsize polarita_zfs/data/postgres) == 8192 ]]
[[ $(zfs get -H -o value keystatus polarita_zfs/data/postgres) == available ]]
# Stejný adresář je v instanci rodičem db, pool a pki. Služby jím musí
# projít i během opakovaného tofu plan. Data samotná zůstávají v db s 0700.
data=/srv/polarita/data/postgres/test
[[ ! -L $data ]]
if [[ -d $data ]]; then
    chmod 0711 "$data"
else
    install -d -m 0711 "$data"
fi
install -d -m 0700 /srv/polarita/infra/metadata-test
cd "$work/tofu"
image=$(bash "$src/obraz.sh" --alias)
export TF_VAR_postgres_image=local:$image
install -m 0644 "$src/postgres.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
bash "$src/../incus/tofu-init.sh"
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    a = r["change"]["actions"]
    if a in (["no-op"], ["read"]): continue
    if r["address"] == "incus_instance.postgres" and a in (["create"],["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
incus exec -T postgres-test -- bash -ec 'for i in {1..60}; do if mountpoint -q /run && test -S /run/systemd/private && ip -4 -o addr show dev eth0 | grep -q "10.239.33.12/"; then exit 0; fi; sleep 1; done; exit 1'
# Původní obraz určil pouze vytvoření instance. Verze živé instalace ověřuje přímo dpkg.
incus exec -T postgres-test -- sh -ec 'dir=/var/lib/polarita-postgres/db; test ! -e "$dir/PG_VERSION" || test "$(cat "$dir/PG_VERSION")" = 18'
mapfile -t packages < <(python3 -c 'import json,sys; print(*(k+"="+v for k,v in json.load(open(sys.argv[1]))["packages"].items()), sep="\n")' "$src/postgres.lock.json")
[[ ${#packages[@]} -gt 0 ]]
db=(incus exec -T postgres-test --)
pool_before=$("${db[@]}" dpkg-query -W -f='${Version}' pgbouncer)
bash "$src/../incus/balicky.sh" postgres-test "${packages[@]}"
"${db[@]}" bash -se -- "$pool_before" <<'UPDATE'
set -euo pipefail
services=()
if systemctl is-active --quiet polarita-postgres.service; then
    active=$(runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 -c 'SHOW server_version')
    binary=$(/usr/lib/postgresql/18/bin/postgres --version)
    if [[ $active != "${binary#postgres (PostgreSQL) }" ]]; then services+=(polarita-postgres.service); fi
fi
if systemctl is-active --quiet polarita-pgbouncer.service; then
    if [[ ${#services[@]} -gt 0 || $(dpkg-query -W -f='${Version}' pgbouncer) != "$1" ]]; then services+=(polarita-pgbouncer.service); fi
fi
if [[ ${#services[@]} -gt 0 ]]; then systemctl restart "${services[@]}"; fi
UPDATE
incus exec -T postgres-test -- bash -se <"$src/konfigurace.sh"
incus file pull postgres-test/var/lib/polarita-postgres/pki/server.crt "$work/ca.crt"
tofu plan -input=false -detailed-exitcode
