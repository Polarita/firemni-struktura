"""Obnoví účty místních služeb pro Zulip z přístupů doručených do tmpfs."""
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import tempfile
import time

if os.geteuid() or socket.gethostname().split(".")[0] != "zulip-fronta-test":
    raise SystemExit("Úloha patří do vlastní fronty Zulipu")
os.umask(0o077)
root = Path("/run/polarita-zulip-fronta")
root.mkdir(mode=0o755, exist_ok=True)
root.chmod(0o755)
secrets = Path("/run/secrets")
for path in (root, secrets):
    if subprocess.check_output(["findmnt","-n","-o","FSTYPE","-T",path]).strip() != b"tmpfs":
        raise RuntimeError("Přístup fronty vyžaduje tmpfs")

for _ in range(60):
    if all((secrets/key).is_file() for key in ("zulip__memcached_password","zulip__rabbitmq_password")):
        break
    time.sleep(1)
with tempfile.TemporaryDirectory(dir=root) as tmp:
    temp = Path(tmp)
    password = (secrets/"zulip__memcached_password").read_bytes()
    db = temp/"sasldb2"
    subprocess.run(["saslpasswd2","-a","memcached","-f",db,"-u","localhost","-c","-p","zulip"],
                   input=password+b"\n", check=True)
    os.chown(db,0,pwd.getpwnam("memcache").pw_gid)
    db.chmod(0o640)
    db.replace(root/"sasldb2")

    password = (secrets/"zulip__rabbitmq_password").read_bytes()
    salt = hashlib.sha256(b"polarita/zulip/rabbitmq\0"+password).digest()[:4]
    hashed = base64.b64encode(salt+hashlib.sha256(salt+password).digest()).decode()
    definitions = {
        "users":[{"name":"zulip","password_hash":hashed,"hashing_algorithm":"rabbit_password_hashing_sha256","tags":[]}],
        "vhosts":[{"name":"/"}],
        "permissions":[{"user":"zulip","vhost":"/","configure":".*","write":".*","read":".*"}],
    }
    dest = temp/"definitions.json"
    dest.write_text(json.dumps(definitions))
    uid = pwd.getpwnam("rabbitmq").pw_uid
    os.chown(temp,uid,-1)
    os.chown(dest,uid,-1)
    subprocess.run(["rabbitmqctl","-q","import_definitions",dest],check=True)
subprocess.run(["rabbitmqctl","-q","list_user_permissions","zulip"],check=True)
