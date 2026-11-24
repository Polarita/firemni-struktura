"""Připraví izolované databáze bez zásahu do tabulek výrobců. Spouští se uvnitř postgres-test."""
import base64
import hashlib
import hmac
import os
from pathlib import Path
import re
import socket
import subprocess


def sql(query, database="postgres"):
    result = subprocess.run(["runuser", "-u", "postgres", "--", "psql", "-XqAt", "-v", "ON_ERROR_STOP=1",
                             "-d", database], input=query, text=True, capture_output=True)
    if result.returncode:
        # Příkaz při změně hesla obsahuje SCRAM verifier.
        raise RuntimeError(f"SQL operace v {database} skončila kódem {result.returncode}")
    return result.stdout.strip()


def encoded(data):
    return base64.b64encode(data).decode("ascii")


def verifier(password, current):
    salt = os.urandom(16)
    iterations = 16384
    previous = re.fullmatch(r"SCRAM-SHA-256\$(\d+):([A-Za-z0-9+/=]+)\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+", current)
    if previous and int(previous[1]) == iterations:
        salt = base64.b64decode(previous[2], validate=True)
    salted = hashlib.pbkdf2_hmac("sha256", password, salt, iterations)
    client = hmac.digest(salted, b"Client Key", "sha256")
    stored = hashlib.sha256(client).digest()
    server = hmac.digest(salted, b"Server Key", "sha256")
    return f"SCRAM-SHA-256${iterations}:{encoded(salt)}${encoded(stored)}:{encoded(server)}"


def main():
    if socket.gethostname().split(".")[0] != "postgres-test" or os.geteuid() != 0:
        raise SystemExit("Úloha patří správci v postgres-test")
    # Jména předává instalační skript z jediného seznamu v trezor/pristupy.py.
    import sys
    names = sys.argv[1:]
    if len(set(names)) != 15 or len(names) != 15 or not all(re.fullmatch(r"[a-z][a-z0-9_]+", n) for n in names):
        raise ValueError("Nesouhlasí definice databází")
    for name in names:
        path = Path("/run/secrets/pg-" + name)
        if subprocess.check_output(["findmnt", "-n", "-o", "FSTYPE", "-T", path], text=True).strip() != "tmpfs":
            raise RuntimeError("Tajemství vyžaduje tmpfs")
        if path.is_symlink() or path.stat().st_mode & 0o777 != 0o400:
            raise RuntimeError("Nesprávná oprávnění strojového hesla")
        if sql(f"SELECT 1 FROM pg_roles WHERE rolname='{name}'") != "1":
            sql(f"CREATE ROLE {name} LOGIN")
        current = sql(f"SELECT rolpassword FROM pg_authid WHERE rolname='{name}'")
        wanted = verifier(path.read_bytes(), current)
        if wanted != current:
            sql(f"ALTER ROLE {name} PASSWORD '{wanted}'")
        if sql(f"SELECT 1 FROM pg_database WHERE datname='{name}'") != "1":
            sql(f"CREATE DATABASE {name} TEMPLATE template0")
        sql(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC; GRANT CONNECT, TEMPORARY ON DATABASE {name} TO {name}")
        sql(f"REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE, CREATE ON SCHEMA public TO {name}", name)
    sql("REVOKE ALL ON DATABASE postgres, template1 FROM PUBLIC")
    sql("CREATE SCHEMA IF NOT EXISTS wms", "db_eshop")
    sql("CREATE SCHEMA IF NOT EXISTS polarita", "db_paperclip")
    sql("CREATE SCHEMA IF NOT EXISTS polarita; CREATE SCHEMA IF NOT EXISTS vault_search; "
        "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA vault_search", "db_erp_lhutnik")
    for name in ("db_hr_lide", "db_gdpr_zkousky"):
        sql("CREATE EXTENSION IF NOT EXISTS pgcrypto", name)
    print("PostgreSQL připravil 6 doménových a 9 servisních databází se samostatnými účty.")


if __name__ == "__main__":
    main()
