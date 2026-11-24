"""Inicializace osobního testovacího účtu přes klientské rozhraní Vaultwardenu."""
from base64 import b64decode, b64encode
import fcntl
from hashlib import pbkdf2_hmac
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from uuid import NAMESPACE_DNS, uuid5

from cryptography.hazmat.primitives import hashes, hmac, padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

from pozvanka import EMAIL, INSTANCE, invite, run

BASE = "http://127.0.0.1:8080/hesla/"
HTTP = build_opener(ProxyHandler({}))
ORG = "Polarita TEST"
COLLECTIONS = (
    "11 Vedení a governance", "12 Marketing a růst", "13 Obchod a logistika",
    "14 Elektro služby a akademie", "15 Právo a technické normy", "16 Finance a kancelář",
    "17 IT a bezpečnost", "18 Lidé a terénní realizace",
)
ITERATIONS = 600_000


def b64(value):
    return b64encode(value).decode("ascii")


def request(path, body=None, token=None, form=False):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        data = (urlencode(body) if form else json.dumps(body)).encode()
    if token:
        headers["Authorization"] = "Bearer " + token
    with HTTP.open(Request(BASE + path, data=data, headers=headers), timeout=20) as res:
        raw = res.read()
        return json.loads(raw) if raw else None


# Formáty EncString podporované Bitwardenem. Každý zápis používá nový IV.
def seal(key, data):
    iv = os.urandom(16)
    pad = padding.PKCS7(128).padder()
    enc = Cipher(algorithms.AES(key[:32]), modes.CBC(iv)).encryptor()
    ciphertext = enc.update(pad.update(data) + pad.finalize()) + enc.finalize()
    mac = hmac.HMAC(key[32:], hashes.SHA256())
    mac.update(iv + ciphertext)
    return "2." + "|".join(map(b64, (iv, ciphertext, mac.finalize())))


def unseal(key, encoded):
    kind, raw = encoded.split(".", 1)
    if kind != "2":
        raise ValueError("Neznámý formát šifrovaných dat")
    iv, ciphertext, tag = [b64decode(x, validate=True) for x in raw.split("|")]
    mac = hmac.HMAC(key[32:], hashes.SHA256())
    mac.update(iv + ciphertext)
    mac.verify(tag)
    dec = Cipher(algorithms.AES(key[:32]), modes.CBC(iv)).decryptor()
    unpad = padding.PKCS7(128).unpadder()
    return unpad.update(dec.update(ciphertext) + dec.finalize()) + unpad.finalize()


def key_pair(key):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pkcs8 = private.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
    spki = private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return {"publicKey": b64(spki), "encryptedPrivateKey": seal(key, pkcs8)}


def register(stretched, authentication):
    verification = request("identity/accounts/register/send-verification-email",
                           {"email": EMAIL, "name": "Správce TEST"})
    user_key = os.urandom(64)
    request("identity/accounts/register/finish", {
        "email": EMAIL, "emailVerificationToken": verification,
        "key": seal(stretched, user_key), "masterPasswordHash": authentication,
        "kdf": 0, "kdfIterations": ITERATIONS, "keys": key_pair(user_key),
    })


def memberships(token):
    return [org for org in request("api/accounts/profile", token=token)["organizations"] if org["name"] == ORG]


def configure_collections(login, stretched, read_only):
    token = login["access_token"]
    user_key = unseal(stretched, login["Key"])
    private = serialization.load_der_private_key(unseal(user_key, login["PrivateKey"]), None)
    # EncString 3 šifruje klíč organizace veřejným RSA klíčem člena (OAEP SHA-256).
    oaep = rsa_padding.OAEP(mgf=rsa_padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    orgs = memberships(token)
    if not orgs and not read_only:
        org_key = os.urandom(64)
        request("api/organizations", {
            "name": ORG, "billingEmail": EMAIL, "collectionName": seal(org_key, COLLECTIONS[0].encode()),
            "key": "3." + b64(private.public_key().encrypt(org_key, oaep)),
            "keys": key_pair(org_key), "planType": 0,
        }, token)
        orgs = memberships(token)
    if len(orgs) != 1 or orgs[0]["type"] != 0:
        raise RuntimeError("Chybí jednoznačný testovací vlastník organizace")
    org = orgs[0]
    kind, wrapped = org["key"].split(".", 1)
    if kind != "3":
        raise RuntimeError("Neočekávaný typ klíče organizace TEST")
    key = private.decrypt(b64decode(wrapped, validate=True), oaep)

    def names():
        return [unseal(key, c["name"]).decode() for c in request("api/sync", token=token)["collections"]
                if c["organizationId"] == org["id"]]

    existing = names()
    for name in COLLECTIONS:
        if name not in existing and not read_only:
            request("api/organizations/" + org["id"] + "/collections",
                    {"name": seal(key, name.encode()), "groups": [], "users": []}, token)
    verified = names()
    if any(verified.count(name) != 1 for name in COLLECTIONS):
        raise RuntimeError("Klient nepřečetl všechny šifrované kolekce")
    print("Správce odemkl testovací trezor a přečetl osm kolekcí oddělení 11–18.", flush=True)


def client(register_new):
    if not request("api/config")["settings"]["disableUserRegistration"]:
        raise RuntimeError("Registrace je otevřena")
    try:
        request("identity/accounts/register/send-verification-email", {"email": "bez-pozvanky@polarita.test"})
    except HTTPError as error:
        if error.code != 400:
            raise
    else:
        raise RuntimeError("Cizí adresa získala registraci")
    password = Path("/srv/polarita/data/bootstrap-test/test-login/heslo").read_bytes().rstrip(b"\r\n")
    master = pbkdf2_hmac("sha256", password, EMAIL.encode(), ITERATIONS)
    stretched = b"".join(HKDFExpand(hashes.SHA256(), 32, label).derive(master) for label in (b"enc", b"mac"))
    authentication = b64(pbkdf2_hmac("sha256", master, password, 1))
    fields = {"grant_type": "password", "username": EMAIL, "password": authentication, "scope": "api offline_access",
              "client_id": "web", "deviceType": 10, "deviceName": "Polarita TEST",
              "deviceIdentifier": str(uuid5(NAMESPACE_DNS, "instalace.vaultwarden.polarita.test"))}
    try:
        login = request("identity/connect/token", fields, form=True)
    except HTTPError as error:
        if error.code != 400:
            raise
        if not register_new:
            sys.exit(42)
        register(stretched, authentication)
        login = request("identity/connect/token", fields, form=True)
    configure_collections(login, stretched, "--jen-cteni" in sys.argv)


def in_network(register_new):
    state = json.loads(run("incus", "query", "/1.0/instances/" + INSTANCE + "/state"))
    pid = state["pid"]
    if state["status"] != "Running" or pid <= 1:
        raise RuntimeError("Testovací instance neběží")
    args = ["nsenter", "--net=/proc/" + str(pid) + "/ns/net", "--", sys.executable, __file__, "--klient"]
    if register_new:
        args.append("--registrace")
    return subprocess.run(args, check=False).returncode


if __name__ == "__main__":
    if run("hostname", "-s").strip() != b"polarita-hq":
        sys.exit("Inicializace patří do firemní VM")
    if "--klient" in sys.argv:
        client("--registrace" in sys.argv)
    else:
        with Path("/srv/polarita/infra/vaultwarden-test/.ucet").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            code = in_network(False)
            if code == 42:
                invite()
                code = in_network(True)
            sys.exit(code)
