"""Kontrola TLS, přístupu k jednotlivým DB, maskování a uzamčení řady na dočasných datech."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

PKI = "/var/lib/polarita-postgres/pki/server.crt"


def psql(query, database, user="postgres", port=None, passfile=None, reject=False):
    env = dict(os.environ, LC_ALL="C", PGCONNECT_TIMEOUT="4")
    args = ["/usr/lib/postgresql/18/bin/psql", "-XqAtw", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", database]
    identity = {}
    if port:
        env.update(PGSSLMODE="verify-full", PGSSLROOTCERT=PKI, PGPASSFILE=passfile)
        args.extend(["-h", "127.0.0.1", "-p", str(port)])
    else:
        identity = {"user": "postgres", "group": "postgres", "extra_groups": []}
    result = subprocess.run(args, input=query, text=True, env=env, capture_output=True, timeout=30, **identity)
    if reject:
        if result.returncode and reject in result.stderr:
            return ""
        raise RuntimeError(f"Chybné zamítnutí pro {user} v {database}")
    if result.returncode:
        raise RuntimeError(f"Kontrola účtu {user} v {database} na portu {port} selhala")
    return result.stdout.strip()


def masked(database, schema, role):
    psql(f"CREATE SCHEMA {schema}", database)
    try:
        psql(f"""CREATE TABLE {schema}.zkouska (person_no integer PRIMARY KEY, soukrome bytea);
                 INSERT INTO {schema}.zkouska VALUES (1, gen_random_bytes(16));
                 CREATE VIEW {schema}.prehled AS SELECT person_no, TRUE AS zpusobily FROM {schema}.zkouska;
                 GRANT USAGE ON SCHEMA {schema} TO {role};
                 GRANT SELECT ON {schema}.prehled TO {role}""", database)
        if psql(f"SET ROLE {role}; SELECT * FROM {schema}.prehled", database) != "1|t":
            raise RuntimeError("Maskovaný pohled neodpověděl")
        psql(f"SET ROLE {role}; SELECT soukrome FROM {schema}.zkouska", database, reject="permission denied")
    finally:
        psql(f"DROP SCHEMA {schema} CASCADE", database)


def main():
    if socket.gethostname().split(".")[0] != "postgres-test":
        raise RuntimeError("Test patří do postgres-test")
    names = sys.argv[1:]
    if len(names) != 15 or len(set(names)) != 15:
        raise RuntimeError("Chybný počet testovaných účtů")
    with tempfile.NamedTemporaryFile(mode="w", dir="/dev/shm") as f:
        for name in names:
            value = Path("/run/secrets/pg-" + name).read_text()
            f.write(f"127.0.0.1:*:*:{name}:{value}\n")
        f.flush()
        for name in names:
            for port in (5432, 6432):
                actual = psql("SELECT current_database(),current_user,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()",
                              name, name, port, f.name)
                if actual != f"{name}|{name}|TLSv1.3":
                    raise RuntimeError("Chybná trasa nebo šifrování " + name)
        psql("SELECT 1", "db_hr_lide", "keycloak", 5432, f.name, reject="no pg_hba.conf entry")
        psql("SELECT 1", "db_hr_lide", "keycloak", 6432, f.name, reject="failed")
    role = "polarita_ai_masked"
    if psql(f"SELECT count(*) FROM pg_roles WHERE rolname='{role}'", "postgres") == "0":
        psql(f"CREATE ROLE {role} NOLOGIN", "postgres")
    schema = "overeni_" + secrets.token_hex(6)
    for database in ("db_hr_lide", "db_gdpr_zkousky"):
        masked(database, schema, role)
    database = "db_erp_lhutnik"
    psql(f"CREATE SCHEMA {schema}", database)
    try:
        psql(f"CREATE TABLE {schema}.rady (rada text PRIMARY KEY, hodnota integer); "
             f"INSERT INTO {schema}.rady VALUES ('ORG-UOL', 0)", database)
        def increment(_):
            return int(psql(f"BEGIN; SELECT hodnota FROM {schema}.rady WHERE rada='ORG-UOL' FOR UPDATE; "
                            f"UPDATE {schema}.rady SET hodnota=hodnota+1 WHERE rada='ORG-UOL' RETURNING hodnota; "
                            "COMMIT", database).splitlines()[-1])
        with ThreadPoolExecutor(max_workers=10) as pool:
            if sorted(pool.map(increment, range(10))) != list(range(1, 11)):
                raise RuntimeError("Řada vrátila duplicitní nebo chybějící číslo")
    finally:
        psql(f"DROP SCHEMA {schema} CASCADE", database)
    print("TLS 1.3, 15 přímých a 15 poolovaných připojení. Přístup účtu Keycloak do HR zamítnut.")
    print("Oba maskované pohledy čitelné, surová tabulka pro ai zakázána. Deset souběžných transakcí přidělilo 1 až 10.")


if __name__ == "__main__":
    main()
