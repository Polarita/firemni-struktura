"""Založí strojovou identitu TEST pro organizační pečeť a místní simulátor časových razítek."""
import base64
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def new_bundle():
    now = datetime.now(timezone.utc)
    root = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    def identity(cn):
        return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Polarita TEST"),
                          x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    root_name = identity("TEST root - Polarita")
    def certificate(name, key, *, ca=False, timestamp=False):
        usage = x509.KeyUsage(digital_signature=not ca, content_commitment=not ca and not timestamp,
                              key_encipherment=False, data_encipherment=False, key_agreement=False,
                              key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False)
        b = (x509.CertificateBuilder().subject_name(name).issuer_name(root_name)
             .public_key(key.public_key()).serial_number(x509.random_serial_number())
             .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
             .add_extension(x509.BasicConstraints(ca=ca, path_length=0 if ca else None), critical=True)
             .add_extension(usage, critical=True)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
             .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root.public_key()), critical=False))
        if timestamp:
            b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
        return b.sign(root, hashes.SHA256())
    def cert64(cert):
        return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
    bundle = {"ca": cert64(certificate(root_name, root, ca=True))}
    for role, label in (("pecet", "Organizacni pecet TEST"), ("tsa", "Mistni casove razitko TEST")):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        bundle[role + "_cert"] = cert64(certificate(identity(label), key, timestamp=role == "tsa"))
        bundle[role + "_key"] = base64.b64encode(key.private_bytes(serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption())).decode()
    return bundle
