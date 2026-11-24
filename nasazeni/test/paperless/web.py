"""Spustí upstream s6 a služby Paperless s údaji z OpenBao uvnitř firemní VM."""
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

conf = Path("/etc/polarita-paperless")
url = (conf / "url").read_text().strip()
host = urlsplit(url).hostname
if not host or not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host) or url != f"https://{host}:8448":
    raise RuntimeError("Neplatná adresa archivu")
# s6 kopíruje prostředí služeb do /run/s6/container_environment.
runtime = Path("/run/s6")
runtime.mkdir(mode=0o755, exist_ok=True)
if subprocess.check_output(["findmnt", "-no", "FSTYPE", "-T", runtime], text=True).strip() != "tmpfs":
    subprocess.run(["mount", "-t", "tmpfs", "-o", "size=32m,mode=0755,nosuid,nodev", "tmpfs", runtime], check=True)


def secret(key):
    p = Path("/run/secrets") / key
    if (p.is_symlink() or p.stat().st_uid != 0 or p.stat().st_mode & 0o777 != 0o400
            or subprocess.check_output(["findmnt", "-no", "FSTYPE", "-T", p], text=True).strip() != "tmpfs"):
        raise RuntimeError("Neočekávaný zdroj strojového údaje")
    s = p.read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,128}", s):
        raise ValueError("Chybný formát strojového údaje")
    return s


provider = {"provider_id": "keycloak", "name": "Ředitelství Polarity", "client_id": "paperless",
            "secret": secret("paperless-oidc_secret"),
            "settings": {"server_url": f"https://{host}/identita/realms/polarita",
                         "token_auth_method": "client_secret_basic"}}
os.environ.update({
    "PAPERLESS_URL": url, "PAPERLESS_BIND_ADDR": "10.239.32.21",
    "PAPERLESS_COOKIE_PREFIX": "polarchiv_", "PAPERLESS_PROXY_SSL_HEADER": '["HTTP_X_FORWARDED_PROTO","https"]',
    "PAPERLESS_DBENGINE": "postgresql", "PAPERLESS_DBHOST": "10.239.33.12", "PAPERLESS_DBPORT": "5432",
    "PAPERLESS_DBNAME": "paperless", "PAPERLESS_DBUSER": "paperless", "PAPERLESS_DBPASS": secret("pg-paperless"),
    "PAPERLESS_DBSSLMODE": "verify-full", "PAPERLESS_DBSSLROOTCERT": str(conf / "postgres.crt"),
    "PAPERLESS_REDIS": "unix:///run/paperless-broker/valkey.sock",
    "PAPERLESS_DATA_DIR": "/var/lib/polarita-paperless/data", "PAPERLESS_MEDIA_ROOT": "/var/lib/polarita-paperless/media",
    "PAPERLESS_CONSUMPTION_DIR": "/var/lib/polarita-paperless/consume",
    "PAPERLESS_TASK_WORKERS": "1", "PAPERLESS_THREADS_PER_WORKER": "1", "PAPERLESS_WEBSERVER_WORKERS": "1",
    "PAPERLESS_OCR_LANGUAGE": "ces", "PAPERLESS_TIME_ZONE": "Europe/Prague", "PAPERLESS_SECRET_KEY": secret("paperless-secret"),
    "PAPERLESS_APPS": "allauth.socialaccount.providers.openid_connect",
    "PAPERLESS_SOCIALACCOUNT_PROVIDERS": json.dumps({"openid_connect": {"APPS": [provider]}}),
    "PAPERLESS_ACCOUNT_ALLOW_SIGNUPS": "false", "PAPERLESS_SOCIALACCOUNT_ALLOW_SIGNUPS": "true",
    "PAPERLESS_SOCIAL_AUTO_SIGNUP": "true", "PAPERLESS_DISABLE_REGULAR_LOGIN": "true",
    "PAPERLESS_REDIRECT_LOGIN_TO_SSO": "true", "REQUESTS_CA_BUNDLE": str(conf / "oidc.crt"),
})
os.execv("/init", ["/init"])
