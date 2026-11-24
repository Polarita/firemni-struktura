"""Připraví první import realmu v šifrovaném úložišti. Další start zachová uživatelský stav."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlparse

clients = {
    "headscale": "https://vpn.polarita.cz/oidc/callback",
    "decisions": "https://decisions.int.polarita.cz/oauth2/callback",
    "zulip": "https://zulip.int.polarita.cz/complete/oidc/",
    "gitea": "https://gitea.int.polarita.cz/user/oauth2/keycloak/callback",
    "paperless": "https://paperless.int.polarita.cz/accounts/oidc/keycloak/login/callback/",
    "vikunja": "https://vikunja.int.polarita.cz/auth/openid/keycloak",
    "moodle": "https://akademie.polarita.cz/admin/oauth2callback.php",
    "portal-spolupracovniku": "https://spolupracovnici.polarita.cz/oidc/callback",
    "web-objekt-klient": "https://objekt.polarita.cz/oidc/callback",
    "umami": "https://umami.int.polarita.cz/oauth2/callback",
    "oauth2-proxy-chatwoot": "https://chatwoot.int.polarita.cz/oauth2/callback",
    "oauth2-proxy-silverbullet": "https://vault.int.polarita.cz/oauth2/callback",
}

def main():
    import_dir = Path("/srv/polarita/data/bootstrap-test/keycloak-test/import")
    url = urlparse(sys.argv[1])
    if url.scheme != "https" or url.path != "/identita" or not url.hostname:
        raise RuntimeError("Chybný veřejný název realmu")
    os.umask(0o077)
    import_dir.mkdir(parents=True, mode=0o755, exist_ok=True)
    import_dir.chmod(0o755)
    target = import_dir / "polarita-realm.json"
    if target.exists():
        return
    password = Path("/srv/polarita/data/bootstrap-test/test-login/heslo").read_bytes().rstrip(b"\r\n")
    salt = secrets.token_bytes(32)
    iterations = 210000
    hashed = hashlib.pbkdf2_hmac("sha512", password, salt, iterations, dklen=64)
    credential = {"type": "password", "temporary": False,
                  "credentialData": json.dumps({"algorithm": "pbkdf2-sha512", "hashIterations": iterations}),
                  "secretData": json.dumps({"value": base64.b64encode(hashed).decode(),
                                            "salt": base64.b64encode(salt).decode()})}
    realm = {"realm": "polarita", "displayName": "Ředitelství Polarity", "enabled": True,
             "registrationAllowed": False, "resetPasswordAllowed": False, "rememberMe": False,
             "sslRequired": "external", "bruteForceProtected": True, "defaultLocale": "cs",
             "internationalizationEnabled": True, "supportedLocales": ["cs", "en"],
             "roles": {"realm": [{"name": "break-glass-approver"}, {"name": "spravce-test"}]},
             "clients": [{"clientId": name, "protocol": "openid-connect", "publicClient": False,
                          "enabled": False, "secret": secrets.token_urlsafe(40), "standardFlowEnabled": True,
                          "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
                          "serviceAccountsEnabled": False, "redirectUris": [callback]}
                         for name, callback in clients.items()],
             "users": [{"username": "spravce", "firstName": "Správce", "lastName": "TEST", "enabled": True,
                        "email": "spravce@polarita.test", "emailVerified": True,
                        "realmRoles": ["default-roles-polarita", "spravce-test"], "credentials": [credential]}]}
    temp = import_dir / ".novy"
    temp.write_text(json.dumps(realm, ensure_ascii=False))
    os.chown(temp, 1000, 0)
    temp.chmod(0o400)
    temp.replace(target)

if __name__ == "__main__":
    main()
