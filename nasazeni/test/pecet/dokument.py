"""Testovací organizační pečeť PAdES se samostatným místním simulátorem razítka RFC 3161."""
import base64
import io
import json
from pathlib import Path
import sys

ALLOWED = {"predavaci-protokol", "seznameni-monitoring", "archivni-kopie-deniku"}


def seal(kind, data, bundle):
    if kind not in ALLOWED:
        raise ValueError("SEAL_NOT_A_PERSONAL_SIGNATURE")
    from asn1crypto import keys, x509
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    from pyhanko.sign.timestamps import DummyTimeStamper
    from pyhanko_certvalidator.registry import SimpleCertificateStore

    anchors = SimpleCertificateStore()
    ca = x509.Certificate.load(base64.b64decode(bundle["ca"], validate=True))
    anchors.register(ca)
    def identity(role):
        cert = x509.Certificate.load(base64.b64decode(bundle[role + "_cert"], validate=True))
        key = keys.PrivateKeyInfo.load(base64.b64decode(bundle[role + "_key"], validate=True))
        return cert, key
    signer = signers.SimpleSigner(*identity("pecet"), cert_registry=anchors, embed_roots=False)
    timestamp = DummyTimeStamper(*identity("tsa"), certs_to_embed=anchors)
    meta = signers.PdfSignatureMetadata(field_name="PolaritaTest", md_algorithm="sha256",
                                        subfilter=fields.SigSeedSubFilter.PADES,
                                        reason="Organizační pečeť v režimu TEST")
    return signers.PdfSigner(meta, signer=signer, timestamper=timestamp).sign_pdf(
        IncrementalPdfFileWriter(io.BytesIO(data))).getvalue()


def verify(data, root):
    from asn1crypto import x509
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign import validation
    from pyhanko_certvalidator import ValidationContext

    ca = x509.Certificate.load(base64.b64decode(root, validate=True))
    ctx = ValidationContext(trust_roots=[ca], allow_fetching=False, revocation_mode="soft-fail")
    reader = PdfFileReader(io.BytesIO(data))
    signatures = reader.embedded_regular_signatures
    if len(signatures) != 1:
        raise ValueError("Chybí jediná očekávaná pečeť")
    status = validation.validate_pdf_signature(signatures[0], ctx, ctx)
    timestamp = status.timestamp_validity
    if not (status.bottom_line and timestamp and timestamp.valid and timestamp.trusted and timestamp.intact):
        raise ValueError("Pečeť nebo testovací časové razítko neprošlo kontrolou")
    if status.signing_cert.subject.native.get("organization_name") != "Polarita TEST":
        raise ValueError("Chybná organizace")


def sample(kind):
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.writer import PdfFileWriter, PageObject

    rows = {
        "predavaci-protokol": ("Predavaci protokol", "Vzorek TEST-001", "Predmet: kontrolni svitidlo ve zkusebne."),
        "seznameni-monitoring": ("Seznameni s provoznim monitoringem", "Vzorek TEST-002", "Obsah: dostupnost zkusebni sluzby."),
        "archivni-kopie-deniku": ("Archivni kopie stavebniho deniku", "Vzorek TEST-003", "Zaznam: cvicna prohlidka zkusebniho pracoviste."),
    }[kind]
    w = PdfFileWriter()
    name = generic.pdf_name
    font = generic.DictionaryObject({name("/Type"): name("/Font"), name("/Subtype"): name("/Type1"),
                                     name("/BaseFont"): name("/Helvetica")})
    resources = generic.DictionaryObject({name("/Font"): generic.DictionaryObject({name("/F1"): w.add_object(font)})})
    lines = ["BT /F1 15 Tf 22 133 Td (Polarita TEST) Tj /F1 11 Tf"]
    for line in rows:
        lines.append("0 -22 Td (" + line + ") Tj")
    lines.append("ET")
    content = generic.StreamObject(stream_data=" ".join(lines).encode("ascii"))
    w.insert_page(PageObject(w.add_object(content), (0, 0, 340, 160), resources))
    output = io.BytesIO()
    w.write(output)
    return output.getvalue()


def main():
    import os
    import stat
    if len(sys.argv) == 3 and sys.argv[1] == "--vzor" and sys.argv[2] in ALLOWED:
        sys.stdout.buffer.write(sample(sys.argv[2]))
        return
    if sys.argv[1:] == ["--verejny-koren"]:
        public_only = True
    elif len(sys.argv) == 3 and sys.argv[1] == "--pecet":
        if sys.argv[2] not in ALLOWED:
            sys.exit("SEAL_NOT_A_PERSONAL_SIGNATURE")
        public_only = False
    elif sys.argv[1:] == ["--overit"]:
        envelope = json.load(sys.stdin)
        verify(base64.b64decode(envelope["pdf"], validate=True), envelope["ca"])
        print("Integrita, původ organizační pečeti a místní časové razítko byly ověřeny.")
        return
    else:
        sys.exit("Použijte --pecet TYP, --verejny-koren, --vzor nebo --overit.")
    path = Path("/run/secrets/pecet-test")
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o400 or st.st_uid != os.geteuid():
        sys.exit("Soubor identity nemá očekávaného vlastníka nebo oprávnění.")
    bundle = json.loads(path.read_text())
    if public_only:
        print(bundle["ca"])
        return
    document = sys.stdin.buffer.read(20 * 1024 * 1024 + 1)
    if len(document) > 20 * 1024 * 1024:
        sys.exit("Překročen limit testovacího dokumentu.")
    sys.stdout.buffer.write(seal(sys.argv[2], document, bundle))


if __name__ == "__main__":
    main()
