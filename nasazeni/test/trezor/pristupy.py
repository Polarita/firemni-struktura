"""Inicializace testovacího Raftu a ověření oddělených rolí. Tajné hodnoty zůstávají v RAM."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

WORK = Path("/srv/polarita/infra/openbao-test")
VAULT = Path("/srv/polarita/data/bootstrap-test/openbao-test")
BASE = "https://10.239.33.10:8200/v1/"
MAINT = "sprava-test"
FIXTURES = {
    "16001-ucetni": ["uol-cteni", "banky-cteni"],
    "17003-spravce-site": ["dns"],
    "14005-zakazky": ["mapy"],
    "fleet-gps-bridge": ["mapy"],
    "12001-marketing": ["reklama-pozastavena"],
    "asterisk": ["sip"],
    "stalwart-jadro": ["dkim"],
    "comm-gateway": ["whatsapp", "chatwoot", "zulip-bot"],
    "pyhanko": ["organizacni-pecet"],
    "reditelstvi-test": ["reditelstvi"],
    "caddy-test": ["caddy"],
    "headscale-test": ["headscale"],
    "stalwart-mx-test": ["stalwart-mx"],
    "11001-ceo": ["agent-11001"],
    "12002-obsah-geo": ["agent-12002"],
    "13001-eshop": ["agent-13001"],
    "13002-nakupci": ["agent-13002"],
    "14001-projektant": ["agent-14001"],
    "14002-rozpoctar": ["agent-14002"],
    "14003-revizak": ["agent-14003"],
    "14004-skolitel": ["agent-14004"],
    "15001-pravni-specialista": ["agent-15001"],
    "15002-normovac": ["agent-15002"],
    "16002-tajemnik": ["agent-16002"],
    "17001-programator": ["agent-17001"],
    "17002-webmaster": ["agent-17002"],
    "17004-klicnik": ["agent-17004"],
    "17005-ai-provoz": ["agent-17005"],
    "18001-personalista": ["agent-18001"],
    "isds-podatelna-bridge": ["stav-podatelny"],
    "openbao-test": ["openbao-agent"],
    "vaultwarden-test": ["vaultwarden-agent"],
    "postgres-test": ["postgres-agent"],
    "pecet-test": ["pecet-agent"],
    "keycloak-test": ["keycloak-agent"],
}
DATABASES = (
    "db_eshop", "db_akademie", "db_erp_lhutnik", "db_gdpr_zkousky", "db_hr_lide", "db_paperclip",
    "keycloak", "paperless", "vikunja", "gitea", "umami", "zulip", "stalwart", "chatwoot", "traccar",
)
CACHES = ("eshop", "akademie", "chatwoot", "zulip")
FIXTURES["valkey-test"] = ["valkey-agent"]
FIXTURES.update({"cache-" + name: ["valkey-klient-" + name] for name in CACHES})
BUCKETS = ("foto-staveb", "foto-flotily", "prevzeti-sanonu", "media-eshopu", "prilohy-akademie",
           "pracovni-vykresy", "stalwart-blobs", "hovory")
FIXTURES["garage-test"] = ["garage-agent"]
FIXTURES.update({"s3-" + name: ["objekty-klient-" + name] for name in BUCKETS})
FIXTURES["gitea-test"] = ["gitea-agent"]
FIXTURES["paperclip-test"] = ["paperclip-agent"]
FIXTURES["paperless-test"] = ["paperless-agent"]
FIXTURES["akademie-test"] = ["akademie-agent"]
FIXTURES["medusa-test"] = ["medusa-agent"]
FIXTURES["umami-test"] = ["umami-agent"]
FIXTURES["vikunja-test"] = ["vikunja-agent"]
FIXTURES["zulip-test"] = ["zulip-agent"]
FIXTURES["dohled-zulip"] = ["dohled-zulip-agent"]
FIXTURES["zulip-fronta-test"] = ["zulip-fronta-agent"]
DATABASE_ACCESS = {"akademie-test": ("db_akademie",), "medusa-test": ("db_eshop",), "umami-test": ("umami",), "paperless-test": ("paperless",), "vikunja-test": ("vikunja",), "paperclip-test": ("db_paperclip",), "zulip-test": ("zulip",), "postgres-test": DATABASES, "keycloak-test": ("keycloak",), "gitea-test": ("gitea",)}
# Skutečné údaje ISDS vydá až oprávněný proces s ověřeným časem a rozhodnutím.
DENIED = ["isds-cteni", "isds-odesilani", "eet-vypnuto", "cizi-vzorek"]
HTTP = None


def request(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    req = Request(BASE + path, data=data, headers=headers, method=method)
    # Při souběhu se sestavením aplikace v TEST odpověď trezoru přesáhla 20 sekund.
    with HTTP.open(req, timeout=90) as res:
        raw = res.read()
    return json.loads(raw) if raw else {}


def protect(name, value):
    path = VAULT / (name + ".cred")
    tmp = path.with_suffix(".next")
    subprocess.run(["systemd-creds", "encrypt", "--with-key=tpm2", "--tpm2-pcrs=7",
                    "--name=" + name, "-", str(tmp)], input=json.dumps(value).encode(), check=True)
    tmp.replace(path)


def recover(name):
    data = subprocess.check_output(["systemd-creds", "decrypt", "--name=" + name,
                                    str(VAULT / (name + ".cred")), "-"])
    return json.loads(data)


def envelope(name, value):
    path = VAULT / name
    tmp = path.with_suffix(".next")
    subprocess.run(["openssl", "cms", "-encrypt", "-binary", "-aes-256-gcm", "-outform", "DER",
                    "-recip", str(WORK / "test-obnova.crt"), "-keyopt", "rsa_padding_mode:oaep",
                    "-keyopt", "rsa_oaep_md:sha256", "-out", str(tmp)], check=True,
                   input=json.dumps(value).encode())
    tmp.replace(path)


def credentials(role, token):
    base = "auth/approle/role/" + role
    role_id = request("GET", base + "/role-id", token=token)["data"]["role_id"]
    secret_id = request("POST", base + "/secret-id", {}, token)["data"]["secret_id"]
    return {"role_id": role_id, "secret_id": secret_id}


def login(creds):
    return request("POST", "auth/approle/login", creds)["auth"]["client_token"]


def allow(path, *caps):
    return 'path ' + json.dumps(path) + ' { capabilities = ' + json.dumps(caps) + ' }\n'


def configure(root):
    def put(path, body):
        return request("POST", path, body, root)
    if "audit-test/" not in request("GET", "sys/audit", token=root)["data"]:
        raise RuntimeError("Chybí souborový audit nakonfigurovaný serverem")
    if "test/" not in request("GET", "sys/mounts", token=root)["data"]:
        put("sys/mounts/test", {"type": "kv", "options": {"version": "2"}})
    if "approle/" not in request("GET", "sys/auth", token=root)["data"]:
        put("sys/auth/approle", {"type": "approle"})

    policy = allow("auth/token/revoke-self", "update") + allow("sys/storage/raft/snapshot", "read")
    # I s tímto oprávněním vyžaduje změna rolí tři obnovovací podíly z Ejpovic.
    policy += allow("sys/generate-root-token/attempt", "read", "update", "delete")
    policy += allow("sys/generate-root-token/update", "update")
    for fixture in sorted({x for values in FIXTURES.values() for x in values} | set(DENIED)):
        policy += allow("test/data/" + fixture, "create", "update")
    policy += allow("test/metadata/pki/organizace-test", "read") + allow("test/data/pki/organizace-test", "create")
    for suffix in ("pki/valkey-test", *("valkey/" + name for name in CACHES), "valkey-overeni/server"):
        policy += allow("test/metadata/" + suffix, "read") + allow("test/data/" + suffix, "create")
    for suffix in ("pki/gitea-test", "pki/garage-test", "medusa/aplikace", "umami/aplikace", "paperclip/aplikace", "vikunja/aplikace", "paperless/aplikace", "zulip/fronta", "zulip/aplikace", *("objekty/" + name for name in BUCKETS)):
        policy += allow("test/metadata/" + suffix, "read") + allow("test/data/" + suffix, "create")
    policy += allow("test/data/zulip/checkmk", "create")
    for name in DATABASES:
        policy += allow("test/metadata/databaze/" + name, "read")
        policy += allow("test/data/databaze/" + name, "create")
    for role, paths in FIXTURES.items():
        acl = allow("auth/token/revoke-self", "update")
        for path in paths:
            acl += allow("test/data/" + path, "read")
        if role == "valkey-test":
            acl += allow("test/data/pki/valkey-test", "read") + allow("test/data/valkey-overeni/server", "read")
        for name in CACHES:
            if role == "cache-" + name:
                acl += allow("test/data/valkey/" + name, "read")
        if role == "paperless-test":
            acl += allow("test/data/paperless/aplikace", "read")
        if role == "akademie-test":
            acl += allow("test/data/valkey/akademie", "read")
        if role == "medusa-test":
            acl += allow("test/data/medusa/aplikace", "read")
        if role == "umami-test":
            acl += allow("test/data/umami/aplikace", "read")
        if role == "vikunja-test":
            acl += allow("test/data/vikunja/aplikace", "read")
        if role == "paperclip-test":
            acl += allow("test/data/paperclip/aplikace", "read")
        if role in ("zulip-test","zulip-fronta-test"):
            acl += allow("test/data/zulip/fronta", "read")
        if role == "zulip-test":
            acl += allow("test/data/zulip/aplikace", "read") + allow("test/data/valkey/zulip", "read")
        if role == "dohled-zulip":
            acl += allow("test/data/zulip/checkmk", "read")
        if role == "gitea-test":
            acl += allow("test/data/pki/gitea-test", "read")
        if role == "garage-test":
            acl += allow("test/data/pki/garage-test", "read")
        for bucket in BUCKETS:
            if role == "s3-" + bucket:
                acl += allow("test/data/objekty/" + bucket, "read")
        if role == "pecet-test":
            acl += allow("test/data/pki/organizace-test", "read")
        for db in DATABASE_ACCESS.get(role, ()):
            acl += allow("test/data/databaze/" + db, "read")
        put("sys/policies/acl/" + role, {"policy": acl})
        put("auth/approle/role/" + role, {"token_policies": [role], "token_no_default_policy": True,
            "token_ttl": "120s", "token_max_ttl": "120s", "secret_id_num_uses": 1, "secret_id_ttl": "120s"})
        base = "auth/approle/role/" + role
        policy += allow(base + "/role-id", "read") + allow(base + "/secret-id", "update")
    put("sys/policies/acl/" + MAINT, {"policy": policy})
    put("auth/approle/role/" + MAINT, {"token_policies": [MAINT], "token_no_default_policy": True,
        "token_ttl": "4m", "token_max_ttl": "4m", "secret_id_bound_cidrs": ["10.239.33.1/32"],
        "token_bound_cidrs": ["10.239.33.1/32"]})
    if not (VAULT / "bao-sprava.cred").exists():
        protect("bao-sprava", credentials(MAINT, root))


def initialize_database_passwords(manager):
    for name in DATABASES:
        try:
            metadata = request("GET", "test/metadata/databaze/" + name, token=manager)["data"]
            version = metadata["versions"][str(metadata["current_version"])]
            if version.get("destroyed") or version.get("deletion_time"):
                raise RuntimeError("Obnovte odstraněné tajemství databáze " + name)
        except HTTPError as err:
            if err.code != 404:
                raise
            request("POST", "test/data/databaze/" + name,
                    {"options": {"cas": 0}, "data": {"heslo": secrets.token_urlsafe(32)}}, manager)


def initialize_seal(manager):
    from pecet_test import new_bundle
    try:
        meta = request("GET", "test/metadata/pki/organizace-test", token=manager)["data"]
        version = meta["versions"][str(meta["current_version"])]
        if version.get("destroyed") or version.get("deletion_time"):
            raise RuntimeError("Obnovte testovací identitu pečeti")
    except HTTPError as err:
        if err.code != 404:
            raise
        request("POST", "test/data/pki/organizace-test",
                {"options": {"cas": 0}, "data": {"sada": json.dumps(new_bundle())}}, manager)


def initialize_cache(manager):
    from tls_test import tls_bundle
    for suffix in ("pki/valkey-test", *("valkey/" + name for name in CACHES), "valkey-overeni/server"):
        try:
            meta = request("GET", "test/metadata/" + suffix, token=manager)["data"]
            version = meta["versions"][str(meta["current_version"])]
            if version.get("destroyed") or version.get("deletion_time"):
                raise RuntimeError("Obnovte odstraněné tajemství Valkey")
        except HTTPError as err:
            if err.code != 404:
                raise
            if suffix == "pki/valkey-test":
                fields = tls_bundle("valkey-test", "10.239.33.13")
            elif suffix == "valkey-overeni/server":
                fields = {}
                for name in CACHES:
                    token = login(credentials("cache-" + name, manager))
                    try:
                        data = request("GET", "test/data/valkey/" + name, token=token)["data"]["data"]
                        fields[name] = hashlib.sha256(data["heslo"].encode()).hexdigest()
                    finally:
                        request("POST", "auth/token/revoke-self", {}, token)
            else:
                fields = {"heslo": secrets.token_urlsafe(32)}
            request("POST", "test/data/" + suffix, {"options": {"cas": 0}, "data": fields}, manager)


def initialize_objects(manager):
    from tls_test import tls_bundle
    for suffix in ("pki/gitea-test", "pki/garage-test", "medusa/aplikace", "umami/aplikace", "paperclip/aplikace", "vikunja/aplikace", "paperless/aplikace", "zulip/fronta", "zulip/aplikace", *("objekty/" + name for name in BUCKETS)):
        try:
            meta = request("GET", "test/metadata/" + suffix, token=manager)["data"]
            version = meta["versions"][str(meta["current_version"])]
            if version.get("destroyed") or version.get("deletion_time"):
                raise RuntimeError("Obnovte odstraněné přihlašovací údaje Garage")
        except HTTPError as err:
            if err.code != 404:
                raise
            if suffix == "pki/gitea-test":
                fields = {"sada": json.dumps({k: secrets.token_urlsafe(48) for k in ("podpis","interni","oauth")})}
            elif suffix == "medusa/aplikace":
                fields = {name: secrets.token_urlsafe(48) for name in ("jwt","cookie")}
            elif suffix == "umami/aplikace":
                fields = {"secret": secrets.token_urlsafe(48), "two_factor": secrets.token_hex(32)}
            elif suffix == "paperclip/aplikace":
                fields = {"auth": secrets.token_urlsafe(48), "jwt": secrets.token_urlsafe(48), "master": secrets.token_hex(32)}
            elif suffix in ("vikunja/aplikace", "paperless/aplikace"):
                fields = {name: secrets.token_urlsafe(48) for name in ("secret", "oidc_secret")}
            elif suffix == "zulip/fronta":
                fields = {name: secrets.token_urlsafe(32) for name in ("rabbitmq_password","memcached_password")}
            elif suffix == "zulip/aplikace":
                fields = {name: secrets.token_urlsafe(48) for name in ("secret_key","oidc_secret")}
            elif suffix == "pki/garage-test":
                fields = tls_bundle("garage-test", "10.239.33.14")
                fields.update({"rpc": secrets.token_hex(32), "admin": secrets.token_hex(32)})
            else:
                fields = {"id": "GK" + secrets.token_hex(12), "tajemstvi": secrets.token_hex(32)}
            request("POST", "test/data/" + suffix, {"options": {"cas": 0}, "data": fields}, manager)


def expect_forbidden(method, path, token, body=None):
    try:
        request(method, path, body, token)
    except HTTPError as err:
        if err.code == 403:
            return
        raise
    raise RuntimeError("Neoprávněný přístup prošel: " + path)


def verify_roles():
    manager = login(recover("bao-sprava"))
    initialize_database_passwords(manager)
    initialize_seal(manager)
    initialize_cache(manager)
    initialize_objects(manager)
    values = {}
    for fixture in sorted({x for paths in FIXTURES.values() for x in paths} | set(DENIED)):
        # Zkouška má vlastní pole a cesty pouze v samostatném testovacím KV.
        values[fixture] = secrets.token_urlsafe(24)
        request("POST", "test/data/" + fixture, {"data": {"vzorek": values[fixture]}}, manager)
    for role, paths in FIXTURES.items():
        token = login(credentials(role, manager))
        for path in paths:
            actual = request("GET", "test/data/" + path, token=token)["data"]["data"]["vzorek"]
            if not secrets.compare_digest(actual, values[path]):
                raise RuntimeError("Neočekávaná hodnota testovacího tajemství")
        other = next(path for path in values if path not in paths and path not in DENIED)
        for path in [other, *DENIED]:
            expect_forbidden("GET", "test/data/" + path, token)
        expect_forbidden("POST", "test/data/" + paths[0], token, {"data": {"vzorek": "zapis"}})
        request("POST", "auth/token/revoke-self", {}, token)
    request("POST", "auth/token/revoke-self", {}, manager)
    print(f"{len(FIXTURES)} rolí: povolené čtení ověřeno, zápis a cizí tajemství odmítnuty.", flush=True)


def main():
    global HTTP
    os.umask(0o077)
    context = ssl.create_default_context(cafile=str(WORK / "ca.crt"))
    HTTP = build_opener(ProxyHandler({}), HTTPSHandler(context=context))
    pending = VAULT / "bao-bootstrap.cred"
    if not request("GET", "sys/init")["initialized"]:
        if pending.exists() or (VAULT / "inicializovano").exists():
            raise RuntimeError("Prázdný Raft nesouhlasí s existujícími údaji instalace")
        output = subprocess.check_output(["incus", "exec", "-T", "openbao-test", "--", "/usr/local/bin/bao",
            "operator", "init", "-address=https://127.0.0.1:8200", "-ca-cert=/var/lib/polarita-openbao/tls/server.crt",
            "-format=json", "-recovery-shares=5", "-recovery-threshold=3"])
        receipt = json.loads(output)
        protect("bao-bootstrap", receipt)
    for _ in range(60):
        if not request("GET", "sys/seal-status")["sealed"]:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Trezor je zapečetěný")
    if pending.exists():
        init = recover("bao-bootstrap")
        shares = init["recovery_keys_b64"]
        if len(shares) != 5 or init["recovery_keys_threshold"] != 3:
            raise RuntimeError("Chybí potvrzení prahu obnovy")
        envelope("obnova-podily.cms", {"threshold": 3, "shares": shares})
        root = init["root_token"]
        try:
            request("GET", "auth/token/lookup-self", token=root)
        except HTTPError as err:
            if err.code != 403:
                raise
        else:
            configure(root)
            verify_roles()
            request("POST", "auth/token/revoke-self", {}, root)
        expect_forbidden("GET", "auth/token/lookup-self", root)
        print("Prvotní root token byl zneplatněn. Obnova používá tři podíly z pěti.")
        (VAULT / "inicializovano").touch(mode=0o600)
        pending.unlink()
    verify_roles()


if __name__ == "__main__":
    if subprocess.check_output(["hostname", "-s"]).strip() != b"polarita-hq":
        sys.exit("Konfigurace patří do VM polarita-hq")
    with (WORK / ".pristupy-lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        main()
