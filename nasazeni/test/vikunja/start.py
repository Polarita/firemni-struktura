"""Sestaví provozní konfiguraci úkolovníku v paměti pod jeho vlastním účtem."""
import json
import os
from pathlib import Path
import re
import sys

from urllib.parse import urlsplit

root = Path("/var/lib/vikunja")
runtime = Path("/run/polarita-vikunja")
public = Path("/etc/polarita-vikunja/url").read_text().strip()
host = urlsplit(public).hostname
if not host or not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host) or public != f"https://{host}:8447/":
    sys.exit("Neplatná adresa úkolovníku")


def secret(name):
    path = Path("/run/secrets") / name
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o777 != 0o400:
        raise RuntimeError("Chybný příjemce strojového údaje")
    value = path.read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,128}", value):
        raise RuntimeError("Chybný formát strojového údaje")
    return value


config = {
    "service": {"secret": secret("vikunja-secret"), "publicurl": public, "rootpath": str(root),
                "interface": "10.239.32.20:3456", "enableregistration": False,
                "enablelinksharing": False, "timezone": "Europe/Prague"},
    "database": {"type": "postgres", "host": "10.239.33.12:5432", "database": "vikunja",
                 "user": "vikunja", "password": secret("pg-vikunja"), "sslmode": "verify-full",
                 "sslrootcert": "/etc/polarita-vikunja/postgres.crt",
                 "maxopenconnections": 4, "maxidleconnections": 1},
    "files": {"basepath": str(root / "files")},
    "auth": {"local": {"enabled": False}, "openid": {"enabled": True, "providers": {"keycloak": {
        "name": "Ředitelství Polarity", "authurl": f"https://{host}/identita/realms/polarita",
        "clientid": "vikunja", "clientsecret": secret("vikunja-oidc_secret"),
        "scope": "openid email profile"}}}},
    "log": {"http": "off", "database": "off"},
}
os.umask(0o077)
tmp = runtime / "config.next"
tmp.write_text(json.dumps(config))
path = runtime / "config.json"
tmp.replace(path)
binary = "/opt/polarita-vikunja/vikunja"
os.execv(binary, [binary, "web", "--config", str(path)])
