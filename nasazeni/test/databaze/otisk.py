"""Sestaví otisk struktury a identity uvnitř PostgreSQL instance. Na stdout zapíše jen SHA-256."""
import hashlib
import subprocess
import sys


def otisk(user):
    def sql(database, query):
        return subprocess.run(["psql", "-XqAtw", "-v", "ON_ERROR_STOP=1", "-h", "/run/postgresql",
                               "-U", user, "-d", database], input=query.encode(),
                              capture_output=True, check=True, timeout=90).stdout

    names = sql("postgres", "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1")
    if len(names.splitlines()) != 15:
        raise ValueError("Nesouhlasí počet databází")
    checks = [names]
    for db in names.decode().splitlines():
        checks.append(sql(db, "select extname,extversion from pg_extension order by 1"))
        checks.append(sql(db, "select schemaname,tablename from pg_tables where schemaname not in "
                              "('information_schema','pg_catalog') order by 1,2"))
    checks.append(sql("postgres", "select rolname,rolpassword from pg_authid join pg_database "
                                  "on rolname=datname where rolcanlogin and not rolsuper order by 1"))
    checks.append(sql("keycloak", "select id,name from realm order by id"))
    checks.append(sql("keycloak", "select id,username from user_entity where username='spravce'"))
    if not checks[-1].strip():
        raise ValueError("Chybí testovací správce v databázi Keycloaku")
    return hashlib.sha256(b"\x00".join(checks)).digest()


if __name__ == "__main__":
    if sys.argv[1:] not in (["postgres"], ["obnova_test"]):
        sys.exit(64)
    try:
        sys.stdout.buffer.write(otisk(sys.argv[1]))
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(65)
    except (subprocess.SubprocessError, OSError):
        sys.exit(75)
