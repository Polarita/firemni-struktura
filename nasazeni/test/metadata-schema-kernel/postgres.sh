#!/bin/bash
# Příprava vlastní domény a jejích místních účtů v postgres-test.
set -euo pipefail
[[ $(hostname -s) == postgres-test && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
base=/opt/polarita-metadata-test
exec 8>/run/polarita-metadata-instalace.lock
flock 8
for user in pol_metadata_api pol_metadata_read pol_prijem_sanonu; do
    if ! getent passwd "$user" >/dev/null; then useradd --system --no-create-home --shell /usr/sbin/nologin "$user"; fi
done
db=(runuser -u postgres -- psql -Xqw -v ON_ERROR_STOP=1 -d db_erp_lhutnik)
"${db[@]}" <<'SQL'
BEGIN;
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_metadata_ddl') THEN CREATE ROLE pol_metadata_ddl NOLOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_metadata_api') THEN CREATE ROLE pol_metadata_api LOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_metadata_read') THEN CREATE ROLE pol_metadata_read LOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_prijem_sanonu') THEN CREATE ROLE pol_prijem_sanonu LOGIN; END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('pol_metadata_ddl','pol_metadata_api','pol_metadata_read','pol_prijem_sanonu')
      AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR rolcanlogin <> (rolname <> 'pol_metadata_ddl')))
      OR EXISTS (SELECT FROM pg_auth_members WHERE member IN ('pol_metadata_ddl'::regrole,'pol_metadata_api'::regrole,'pol_metadata_read'::regrole,'pol_prijem_sanonu'::regrole))
    THEN RAISE EXCEPTION 'Neshoda databázových rolí'; END IF;
END
$roles$;
CREATE SCHEMA IF NOT EXISTS polarita_test_metadata AUTHORIZATION pol_metadata_ddl;
DO $check$
BEGIN
    IF (SELECT nspowner FROM pg_namespace WHERE nspname='polarita_test_metadata') <> 'pol_metadata_ddl'::regrole
    THEN RAISE EXCEPTION 'Schéma má jiného vlastníka'; END IF;
END
$check$;
GRANT CONNECT ON DATABASE db_erp_lhutnik TO pol_metadata_api, pol_metadata_read, pol_prijem_sanonu;
GRANT USAGE ON SCHEMA polarita_test_metadata TO pol_metadata_api, pol_metadata_read;
COMMIT;
SQL
python3 - /etc/polarita-postgres/pg_hba.conf <<'PY'
from pathlib import Path
import os, sys, tempfile
p = Path(sys.argv[1])
lines = p.read_text().splitlines()
needed = ["local db_erp_lhutnik " + user + " peer" for user in ["pol_metadata_api", "pol_metadata_read", "pol_prijem_sanonu"]]
new = [line for line in lines if line not in needed]
anchor = new.index("local all postgres peer")
new[anchor+1:anchor+1] = needed
if new != lines:
    with tempfile.NamedTemporaryFile("w", dir=p.parent, delete=False) as exported:
        exported.write("\n".join(new)+"\n")
        os.fchmod(exported.fileno(), p.stat().st_mode & 0o777)
    os.replace(exported.name, p)
PY
systemctl reload polarita-postgres.service
python3 "$src/generator.py" "$src/vzor.json" "$src/vystup"
{ echo 'SET ROLE pol_metadata_ddl;'; cat "$src/vystup/up.sql"; } | "${db[@]}" >/dev/null
"${db[@]}" <<'SQL'
GRANT SELECT ON polarita_test_metadata.meta_termin TO pol_metadata_read, pol_metadata_api;
GRANT INSERT (popis,dny,vyrizeno), UPDATE (popis,dny,vyrizeno,version) ON polarita_test_metadata.meta_termin TO pol_metadata_api;
SQL
"${db[@]}" <"$src/spisy.sql"
"${db[@]}" <"$src/sanony.sql"
"${db[@]}" <"$src/kniha.sql"
"${db[@]}" <"$src/osa.sql"
"${db[@]}" <"$src/zkouska_knihy.sql"
ln -sfn "$src" "$base/.current.next"
mv -Tf "$base/.current.next" "$base/current"
install -m 0644 "$src/polarita-metadata.service" /etc/systemd/system/polarita-metadata.service
systemctl daemon-reload
systemctl enable polarita-metadata.service
systemctl restart polarita-metadata.service
