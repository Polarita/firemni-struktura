"""Uloží klíč příjmového bota do OpenBao a předá doručovací službě kopii svázanou s vTPM."""
import fcntl
import hmac
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"trezor"))
import pristupy as p

if socket.gethostname().split(".")[0] != "polarita-hq" or os.geteuid():
    raise SystemExit("Příprava přístupu patří do testovací VM")
os.umask(0o077)
with (p.WORK/".zulip-dohled.lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    native = subprocess.check_output(["incus","exec","-T","postgres-test","--","runuser","-u","postgres","--",
        "psql","-XqAt","-v","ON_ERROR_STOP=1","-d","zulip","-c",
        """select u.api_key from zulip.zerver_userprofile u join zulip.zerver_realm r on r.id=u.realm_id
           where u.delivery_email='checkmk-bot@polarita.test' and u.is_bot and u.bot_type=2 and u.is_active
           and r.name='Ředitelství Polarity'"""], text=True).strip()
    if not re.fullmatch(r"[A-Za-z0-9]{32}", native):
        raise RuntimeError("Zulip nepotvrdil právě jeden klíč příjmového bota")
    p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=ssl.create_default_context(cafile=str(p.WORK/"ca.crt"))))
    manager = p.login(p.recover("bao-sprava"))
    path = "test/data/zulip/checkmk"
    try:
        reader = p.login(p.credentials("dohled-zulip", manager))
        try:
            try:
                key = p.request("GET", path, token=reader)["data"]["data"]["api_key"]
            except HTTPError as err:
                if err.code != 404:
                    raise
                p.request("POST", path, {"options":{"cas":0},"data":{"api_key":native}}, manager)
                key = p.request("GET", path, token=reader)["data"]["data"]["api_key"]
            if not hmac.compare_digest(native, key):
                raise RuntimeError("Klíč příjmového bota se liší od hodnoty v trezoru")
            p.expect_forbidden("GET","test/data/zulip/aplikace",reader)
        finally:
            p.request("POST","auth/token/revoke-self",{},reader)
    finally:
        p.request("POST","auth/token/revoke-self",{},manager)
    name = "zulip-webhook"
    if not (p.VAULT/(name+".cred")).is_file() or not hmac.compare_digest(p.recover(name), key):
        p.protect(name, key)
    print("OpenBao potvrdil klíč vyhrazeného bota. Doručovací služba má šifrovaný přístup vázaný na vTPM.")
