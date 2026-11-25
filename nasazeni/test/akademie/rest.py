"""Compliance Bridge TEST přečte známky přes nativní Moodle REST ve VM."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
from urllib.parse import urlencode

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC.parent / "trezor"))
import pristupy as bao

VM = "akademie-test"
FUNCTION = "gradereport_user_get_grade_items"


def credential():
    bao.HTTP = bao.build_opener(bao.ProxyHandler({}), bao.HTTPSHandler(
        context=ssl.create_default_context(cafile=str(bao.WORK / "ca.crt"))))
    manager = bao.login(bao.recover("bao-sprava"))
    try:
        bao.initialize_grade_token(manager)
        reader = bao.login(bao.credentials("compliance-bridge-test", manager))
    finally:
        bao.request("POST", "auth/token/revoke-self", {}, manager)
    try:
        key = bao.request("GET", "test/data/akademie/rest", token=reader)["data"]["data"]["token"]
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ValueError("Neplatný přístup ke známkám v OpenBao.")
        bao.expect_forbidden("GET", "test/data/akademie/aplikace", reader)
        return key
    finally:
        bao.request("POST", "auth/token/revoke-self", {}, reader)


def inside(command, body=b"", user=None):
    args = ["incus", "exec", "-T", VM]
    if user is not None:
        args.extend(["--user", str(user), "--group", str(user)])
    run = subprocess.run(args + ["--", *command], input=body, capture_output=True, timeout=240)
    if run.returncode:
        raise RuntimeError(f"Akademie nedokončila příkaz {command[0]} (kód {run.returncode}).")
    return run.stdout


def call(host, key, function, **params):
    body = urlencode({"wstoken": key, "wsfunction": function, "moodlewsrestformat": "json", **params}).encode()
    result = inside(["curl", "--noproxy", "*", "--silent", "--show-error", "--fail", "--max-time", "150",
                     "--header", "Host: " + host, "--data-binary", "@-",
                     "http://127.0.0.1:8081/webservice/rest/server.php"], body, user=65534)
    return json.loads(result)


def check_grade(result, ids, user):
    if result.get("warnings") != [] or len(result.get("usergrades", [])) != 1:
        raise RuntimeError("Moodle nevrátil očekávaný přehled známek.")
    grade = result["usergrades"][0]
    if grade["userid"] != ids[user] or grade["courseid"] != ids["course"]:
        raise ValueError("Odpověď se týká jiné osoby nebo kurzu.")
    items = [item for item in grade["gradeitems"] if item.get("cmid") == ids["cm"] and item.get("itemmodule") == "offlinequiz"]
    if len(items) != 1 or items[0].get("grademax") != 100 or items[0].get("graderaw") != {"a": 100, "b": 50}[user]:
        raise ValueError("Výsledek Offline Quiz přes REST se liší od naskenovaných archů.")


def main(only_vault):
    key = credential()
    if only_vault:
        print("OpenBao vydal účtu Compliance Bridge přístup ke známkám a odmítl mu klíč OIDC.")
        return
    url = inside(["cat", "/etc/polarita-akademie/url"]).decode().strip()
    if not re.fullmatch(r"https://[a-z0-9.-]+\.ts\.net:8451", url):
        raise ValueError("Neočekávaný původ Akademie.")
    host = url.removeprefix("https://")
    public_status = subprocess.check_output(["curl", "--silent", "--show-error", "--noproxy", "*",
        "--max-time", "20", "--output", "/dev/null", "--write-out", "%{http_code}", "--header", "Host: " + host,
        "http://10.239.32.24:8080/webservice/rest/server.php"])
    if public_status != b"403":
        raise RuntimeError("Hlavní webový vstup nezamítl interní REST rozhraní.")
    dest = "/etc/polarita-akademie/rest.php"
    subprocess.run(["incus", "file", "push", "--mode=0644", str(SRC / "rest.php"), VM + dest + ".next"], check=True)
    inside(["mv", "-T", dest + ".next", dest])
    ids = json.loads(inside(["php8.4", "-d", "zend.exception_ignore_args=1", dest], key.encode(), user=33))
    if set(ids) != {"course", "cm", "a", "b"} or not all(type(n) is int and n > 0 for n in ids.values()):
        raise ValueError("Chybí identifikace účastníků cvičného kurzu.")
    for user in ("a", "b"):
        check_grade(call(host, key, FUNCTION, courseid=ids["course"], userid=ids[user]), ids, user)
    for result, expected in (
            (call(host, key, "core_user_get_users", **{"criteria[0][key]": "username", "criteria[0][value]": "spravce"}), "accessexception"),
            (call(host, key, FUNCTION, courseid=1, userid=ids["a"]), "restrictedcontextexception")):
        if not result.get("exception") or result.get("errorcode") != expected:
            raise ValueError("Služba nepotvrdila omezení na jedinou funkci a cvičný kurz.")
    print("Compliance Bridge přečetl přes Moodle REST dvě známky z Offline Quiz (100 % a 50 %). "
          "Moodle odmítl výpis uživatelů i čtení mimo kurz. OpenBao odmítl účtu bridge čtení klíče OIDC.")


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Bridge patří do firemní VM.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--over-trezor", action="store_true")
    options = parser.parse_args()
    with open("/run/polarita-akademie-rest.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        main(options.over_trezor)
