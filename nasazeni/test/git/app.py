"""Sestaví konfiguraci testovací služby Gitea v paměti až po doručení její identity."""
from pathlib import Path
import base64
import hashlib
import configparser
import json
import os
import tempfile
import time
from urllib.parse import urlparse

secrets = Path("/run/secrets")
config_dir = Path("/run/polarita-gitea")
public = Path("/etc/polarita-gitea/url").read_text().strip()
url = urlparse(public)
if url.scheme != "https" or not url.hostname or url.path != "/git/" or url.username or url.password:
    raise SystemExit("Neplatný soukromý vstup Gitea")
for _ in range(150):
    if all((secrets / f).is_file() for f in ("gitea-stroj", "pg-gitea")):
        break
    time.sleep(1)
machine = json.loads((secrets / "gitea-stroj").read_bytes())
password = (secrets / "pg-gitea").read_text()
if not password or any(not machine.get(k) for k in ("podpis","interni","oauth")):
    raise SystemExit("Chybí hodnoty strojové identity Gitea")
config = configparser.RawConfigParser()
config.optionxform = str
groups = {
    "database": {"DB_TYPE": "postgres", "HOST": "10.239.33.12:5432", "NAME": "gitea", "USER": "gitea",
                 "PASSWD": password, "SSL_MODE": "verify-full", "MAX_OPEN_CONNS": "5", "MAX_IDLE_CONNS": "2"},
    "server": {"PROTOCOL": "http", "HTTP_ADDR":"10.239.32.13", "HTTP_PORT": "3000", "ROOT_URL": public,
               "DOMAIN":url.hostname, "DISABLE_SSH":"true", "OFFLINE_MODE":"true", "APP_DATA_PATH":"/var/lib/gitea/data"},
    "repository": {"ROOT": "/var/lib/gitea/git", "DEFAULT_PRIVATE": "private", "FORCE_PRIVATE": "true"},
    "service": {"DISABLE_REGISTRATION": "false", "ALLOW_ONLY_EXTERNAL_REGISTRATION": "true", "REQUIRE_SIGNIN_VIEW":"true", "ENABLE_NOTIFY_MAIL":"false"},
    "security": {"INSTALL_LOCK":"true", "SECRET_KEY":machine["podpis"], "INTERNAL_TOKEN":machine["interni"],
                 "EGRESS_MODE":"strict", "ALLOWED_HOST_LIST":"127.0.0.1/32:443", "DISABLE_GIT_HOOKS": "true", "DISABLE_WEBHOOKS": "true"},
    "oauth2_client": {"ENABLE_AUTO_REGISTRATION":"true", "USERNAME":"preferred_username", "ACCOUNT_LINKING":"login"},
    "oauth2": {"JWT_SECRET":base64.urlsafe_b64encode(hashlib.sha256(machine["oauth"].encode()).digest()).rstrip(b"=").decode()},
    "picture": {"DISABLE_GRAVATAR":"true", "ENABLE_FEDERATED_AVATAR":"false"},
    "actions": {"ENABLED":"true", "DEFAULT_ACTIONS_URL":"self"},
    "log": {"MODE":"console", "LEVEL":"warn"},
    "mailer": {"ENABLED":"false"},
}
config.read_dict(groups)
with tempfile.NamedTemporaryFile(dir=config_dir, mode="w", delete=False) as out:
    out.write("APP_NAME = Polarita TEST\nWORK_PATH = /var/lib/gitea/data\nRUN_USER = gitea-test\nRUN_MODE = prod\n")
    config.write(out)
    os.fchmod(out.fileno(), 0o400)
    tmp = out.name
os.replace(tmp, config_dir / "app.ini")
