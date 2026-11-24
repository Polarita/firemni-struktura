"""Přenese logickou zálohu PostgreSQL do dočasného Incusu bez síťové karty a ověří obsah."""
from contextlib import ExitStack
import fcntl
import gzip
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

BASE = Path("/srv/polarita/backups/postgres")
DB = "postgres-test"
PG = "/usr/lib/postgresql/18/bin/"


def run(*args, data=b"", timeout=300):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("Operace " + args[0] + " selhala, návratový kód " + str(result.returncode))
    return result.stdout


def inside(name, *args, data=b""):
    return run("incus", "exec", "-T", name, "--", *args, data=data)


def proof(name, user):
    def sql(database, query):
        return inside(name, "runuser", "-u", "postgres", "--", "psql", "-XqAt", "-v", "ON_ERROR_STOP=1",
                      "-h", "/run/postgresql", "-U", user, "-d", database, data=query.encode())
    names = sql("postgres", "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1")
    if len(names.splitlines()) != 15:
        raise RuntimeError("Nesouhlasí počet obnovených databází")
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
        raise RuntimeError("Chybí testovací správce v databázi Keycloaku")
    return hashlib.sha256(b"\x00".join(checks)).digest()


def main():
    if run("hostname", "-s").strip() != b"polarita-hq":
        sys.exit("Zkouška patří do firemní VM")
    os.umask(0o077)
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = run("findmnt", "-n", "-o", "SOURCE", "-T", str(BASE)).decode().strip()
    if not source.startswith("polarita_zfs/") or run("zfs", "get", "-H", "-o", "value", "keystatus", source).strip() != b"available":
        raise RuntimeError("Záloha vyžaduje šifrovaný dataset")
    with ExitStack() as stack:
        lock = stack.enter_context((BASE / ".obnova").open("a"))
        fcntl.flock(lock, fcntl.LOCK_EX)
        tmp = Path(stack.enter_context(tempfile.TemporaryDirectory(dir=BASE)))
        archive = tmp / "cluster.sql.gz"
        original = proof(DB, "postgres")
        with subprocess.Popen(["incus", "exec", "-T", DB, "--", "runuser", "-u", "postgres", "--",
                               PG + "pg_dumpall", "--no-tablespaces"], stdout=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as dump:
            with dump.stdout, gzip.open(archive, "wb", compresslevel=3) as writer:
                shutil.copyfileobj(dump.stdout, writer)
            if dump.wait():
                raise RuntimeError("Export databází selhal")
        image = run("incus", "config", "get", DB, "volatile.base_image").decode().strip()
        if len(image) != 64:
            raise RuntimeError("Chybí otisk databázového obrazu")
        name = "obnova-pg-" + secrets.token_hex(5)
        run("incus", "init", image, name, "-p", "default", "-p", "sandbox_airgap", "-c", "limits.memory=320MiB")
        stack.callback(run, "incus", "delete", "-f", name)
        run("incus", "start", name)
        inside(name, "bash", "-ec", """
for i in {1..60}; do if mountpoint -q /run && test -S /run/systemd/private; then break; fi; sleep 1; done
test "$(ls /sys/class/net)" = lo
install -d -m 0700 -o postgres -g postgres /var/lib/postgresql/obnova
install -d -m 0755 -o postgres -g postgres /run/postgresql
runuser -u postgres -- /usr/lib/postgresql/18/bin/initdb -D /var/lib/postgresql/obnova --username=obnova_test --encoding=UTF8 --locale=C.UTF-8 --auth-local=peer --auth-host=scram-sha-256 >/dev/null
printf 'local all obnova_test peer map=obnova\\nlocal all all peer\\n' >/var/lib/postgresql/obnova/pg_hba.conf
echo 'obnova postgres obnova_test' >/var/lib/postgresql/obnova/pg_ident.conf
runuser -u postgres -- /usr/lib/postgresql/18/bin/pg_ctl -D /var/lib/postgresql/obnova -o "-c listen_addresses='' -c shared_buffers=16MB -c max_connections=12" -l /var/lib/postgresql/obnova/restore.log -w start
""")
        with subprocess.Popen(["incus", "exec", "-T", name, "--", "runuser", "-u", "postgres", "--",
                               "psql", "-Xq", "-v", "ON_ERROR_STOP=1", "-U", "obnova_test", "-d", "postgres"],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as restore:
            with restore.stdin, gzip.open(archive, "rb") as reader:
                shutil.copyfileobj(reader, restore.stdin)
            if restore.wait():
                raise RuntimeError("Import logické zálohy selhal")
        if original != proof(name, "obnova_test"):
            raise RuntimeError("Obnovené databáze, účty nebo obsah realmu se liší")
        os.replace(archive, BASE / "posledni.sql.gz")
    print("Izolovaná obnova 15 databází prošla. Shodují se schémata, tabulky, rozšíření, databázové přístupy a identita správce.")


if __name__ == "__main__":
    main()
