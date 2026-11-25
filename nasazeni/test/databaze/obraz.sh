#!/bin/bash
# APT ověří podepsané indexy ve VM; nezasíťovaná sestavovací instance obdrží pouze balíčky.
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
lock=$src/postgres.lock.json
base=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["base"])' "$lock")
mapfile -t packages < <(python3 -c 'import json,sys;print(*(k+"="+v for k,v in json.load(open(sys.argv[1]))["packages"].items()),sep="\n")' "$lock")
# O aliasu rozhodují pouze vstupy sestavení. Text kompatibility lze aktualizovat samostatně.
key=$(python3 - "$lock" <<'PYKEY'
import hashlib
import json
import sys
with open(sys.argv[1]) as stream:
    record = json.load(stream)
fields = {key: record[key] for key in ("base", "postgresql_major", "packages")}
print(hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16])
PYKEY
)
alias=polarita-postgres-test-$key
if [[ ${1:-} == --alias ]]; then echo "$alias"; exit 0; fi
[[ $# == 0 ]]
work=/srv/polarita/infra/postgres-test
install -d -m 0750 "$work"
exec 9>"$work/.obraz-lock"
flock 9
if incus image info "$alias" >/dev/null 2>&1; then exit 0; fi
tmp=$(mktemp -d "$work/sestaveni-XXXXXXXX")
builder=pg-build-${tmp##*-}
cleanup() {
    if [[ -e $tmp/moje ]]; then incus delete -f "$builder" </dev/null; fi
    rm -rf "$tmp"
}
trap cleanup EXIT
incus init "$base" "$builder" -p default -p sandbox_airgap -c limits.memory=448MiB </dev/null
touch "$tmp/moje"
incus file pull "$builder/var/lib/dpkg/status" "$tmp/status"
install -d "$tmp/deb/partial"
apt-get -o "Dir::State::status=$tmp/status" -o "Dir::Cache::archives=$tmp/deb"     --download-only --no-install-recommends -y install "${packages[@]}"
incus start "$builder"
incus exec -T "$builder" -- sh -ec 'for i in $(seq 1 60); do if test -S /run/systemd/private && mountpoint -q /run; then exit 0; fi; sleep 1; done; exit 1'
incus exec -T "$builder" -- sh -ec 'test "$(ls /sys/class/net)" = lo; install -d /run/pg-deb /etc/postgresql-common; echo "create_main_cluster = false" >/etc/postgresql-common/createcluster.conf; printf "#!/bin/sh\nexit 101\n" >/usr/sbin/policy-rc.d; chmod 0755 /usr/sbin/policy-rc.d'
tar -cf - -C "$tmp/deb" . | incus exec -T "$builder" -- tar -xf - -C /run/pg-deb
incus exec -T "$builder" -- bash -ec 'export DEBIAN_FRONTEND=noninteractive; mkdir -p /run/pg-deb/lists/partial; apt-get -y --no-install-recommends -o Dir::State::Lists=/run/pg-deb/lists -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- -o Dpkg::Options::=--force-confold install /run/pg-deb/*.deb; rm -f /usr/sbin/policy-rc.d; systemctl disable postgresql pgbouncer || exit 1; test -z "$(pg_lsclusters -h)"; test -r /usr/share/postgresql/18/extension/vector.control; test -r /usr/share/postgresql/18/extension/pgcrypto.control; rm -f /etc/ssl/private/ssl-cert-snakeoil.key /etc/ssl/certs/ssl-cert-snakeoil.pem'
incus exec "$builder" -- dpkg-query -W postgresql-18 postgresql-18-pgvector pgbouncer >"$work/balicky-$key.txt"
incus stop "$builder"
incus publish "$builder" --alias "$alias" description="PostgreSQL TEST + PgBouncer podle zámku $key" </dev/null
