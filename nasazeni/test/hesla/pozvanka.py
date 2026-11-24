"""Vydá pozvánku jedinému testovacímu vlastníkovi přes lokální správu Vaultwardenu."""
import json
import secrets
import subprocess
import time
from urllib.parse import urlencode

from argon2 import PasswordHasher

EMAIL = "spravce@polarita.test"
INSTANCE = "vaultwarden-test"
URL = "http://127.0.0.1:8080/hesla"


def run(*args, data=b""):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE, check=True, timeout=120).stdout


def inside(*args, data=b""):
    return run("incus", "exec", "-T", INSTANCE, "--", *args, data=data)


def restart():
    run("incus", "restart", INSTANCE)
    for _ in range(45):
        try:
            inside("curl", "-fsS", "--max-time", "2", URL + "/alive")
            return
        except subprocess.CalledProcessError:
            time.sleep(1)
    raise RuntimeError("Vaultwarden nedokončil start")


def invite():
    if run("hostname", "-s").strip() != b"polarita-hq":
        raise RuntimeError("Pozvánky patří do testovací firemní VM")
    token = secrets.token_urlsafe(32)
    hashed = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=4).hash(token)
    # Incus uchová jen jednosměrný hash. Přihlašovací token vstupuje přes stdin na loopback.
    run("incus", "config", "set", INSTANCE, "environment.ADMIN_TOKEN=" + hashed)
    try:
        restart()
        cookie = "/dev/shm/pozvanka-" + secrets.token_hex(12)
        inside("sh", "-ec", 'test "$(stat -f -c %T /dev/shm)" = tmpfs; umask 077; touch "$1"', "sprava", cookie)
        try:
            inside("curl", "-fsS", "-o", "/dev/null", "-c", cookie, "--data-binary", "@-", URL + "/admin/",
                   data=urlencode({"token": token}).encode())
            code = inside("curl", "-sS", "-b", cookie, "-o", "/dev/null", "-w", "%{http_code}",
                          "-H", "Content-Type: application/json", "--data-binary", "@-", URL + "/admin/invite",
                          data=json.dumps({"email": EMAIL}).encode())
            if code not in (b"200", b"409"):
                raise RuntimeError("Správa nevydala testovací pozvánku, HTTP " + code.decode())
        finally:
            inside("rm", "-f", cookie)
    finally:
        run("incus", "config", "unset", INSTANCE, "environment.ADMIN_TOKEN")
        restart()


if __name__ == "__main__":
    invite()
    print("Pozvánka pro testovacího správce je připravená. Dočasná správa byla vypnuta.")
