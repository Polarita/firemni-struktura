"""Vydá strojovou identitu pro TLS interního Valkey. Materiál drží volající v paměti."""
from datetime import datetime, timezone, timedelta
from ipaddress import ip_address

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def tls_bundle():
    private = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "valkey-test")])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().issuer_name(name).subject_name(name)
                   .public_key(private.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(hours=1)).not_valid_after(now + timedelta(days=365))
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                   .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address("10.239.33.13")),
                                                             x509.DNSName("valkey-test")]), critical=False)
                   .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                   .sign(private, hashes.SHA256()))
    return {"cert": certificate.public_bytes(serialization.Encoding.PEM).decode(),
            "klic": private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()).decode()}
