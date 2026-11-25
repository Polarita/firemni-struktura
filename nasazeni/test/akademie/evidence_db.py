"""Zapíše pseudonymní testovací data přes TLS do dvou oddělených databází."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

GDPR = "db_gdpr_zkousky"
ERP = "db_erp_lhutnik"
ARCHIV = """
INSERT INTO akademie_test.protokol
    (protokol,person_no,druh,provedeno,platnost_do,uspel,komise,sifrovany_obsah,archiv_sha256)
SELECT (j->>'id')::uuid,(j->>'osoba')::uuid,'elektrotechnik',(j->>'provedeno')::timestamptz,
       (j->>'do')::date,true,ARRAY(SELECT jsonb_array_elements_text(j->'komise')::uuid),
       decode(j->>'sifra','base64'),decode(j->>'otisk','hex')
FROM vstup ON CONFLICT (protokol) DO NOTHING;
SELECT to_jsonb(encode(p.sifrovany_obsah,'base64'))
FROM akademie_test.protokol p, vstup
WHERE p.protokol=(j->>'id')::uuid AND p.person_no=(j->>'osoba')::uuid AND p.druh='elektrotechnik'
  AND p.provedeno=(j->>'provedeno')::timestamptz AND p.platnost_do=(j->>'do')::date AND p.uspel
  AND p.komise=ARRAY(SELECT jsonb_array_elements_text(j->'komise')::uuid)
  AND p.archiv_sha256=decode(j->>'otisk','hex');
"""
TERMIN = """
INSERT INTO polarita_test_lhutnik.zkousky (protokol,rozhodnuti,spis,provedeno,platnost_do)
SELECT (j->>'id')::uuid,(j->>'rozhodnuti')::uuid,j->>'spis',
       ((j->>'provedeno')::timestamptz AT TIME ZONE 'Europe/Prague')::date,(j->>'do')::date
FROM vstup ON CONFLICT (protokol) DO NOTHING;
SELECT to_jsonb(z.platnost_do) FROM polarita_test_lhutnik.zkousky z, vstup
WHERE z.protokol=(j->>'id')::uuid AND z.rozhodnuti=(j->>'rozhodnuti')::uuid AND z.spis=j->>'spis'
  AND z.provedeno=((j->>'provedeno')::timestamptz AT TIME ZONE 'Europe/Prague')::date AND z.platnost_do=(j->>'do')::date;
"""


def uloz(database, payload):
    # Proměnná obsahuje jen bezpečnou abecedu Base64 a vstupuje přes stdin.
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    sql = ("BEGIN; CREATE TEMP TABLE vstup ON COMMIT DROP AS SELECT convert_from(decode('" + encoded +
           "','base64'),'UTF8')::jsonb AS j;\n" + {GDPR: ARCHIV, ERP: TERMIN}[database] + "\nCOMMIT;")
    with tempfile.NamedTemporaryFile(mode="w", dir="/dev/shm") as pf:
        password = Path("/run/secrets/pg-" + database).read_text().strip()
        pf.write(f"127.0.0.1:6432:{database}:{database}:{password}\n")
        pf.flush()
        env = dict(os.environ, PGCONNECT_TIMEOUT="15", PGPASSFILE=pf.name, PGSSLMODE="verify-full",
                   PGSSLROOTCERT="/var/lib/polarita-postgres/pki/server.crt")
        result = subprocess.run(["psql", "-XqAtw", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1",
                                 "-p", "6432", "-U", database, "-d", database], input=sql,
                                env=env, capture_output=True, text=True, timeout=120)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("Databáze nepřijala nebo nepotvrdila shodný záznam v " + database)
    return json.loads(result.stdout)


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "postgres-test":
        sys.exit("Evidence vyžaduje postgres-test.")
    print(json.dumps(uloz(sys.argv[1], json.load(sys.stdin))))
