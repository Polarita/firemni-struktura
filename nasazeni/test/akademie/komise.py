"""Převod ověřeného výsledku Moodle a archivovaného osvědčení na komisní protokol TEST."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC.parent / "archiv"))
sys.path.insert(0, str(SRC.parent / "pecet"))
from osvedceni import uloz_a_over_pdf
import zkouska as pecet

PROOF = Path("/srv/polarita/workspace/dukazy/blok-09")
PHP = ["incus", "exec", "-T", "akademie-test", "--user", "33", "--group", "33", "--",
       "php8.4", "-d", "zend.exception_ignore_args=1", "/etc/polarita-akademie/vydani.php"]


def atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as writer:
        tmp = Path(writer.name)
        try:
            writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def pdf_text(pdf):
    command = ["incus", "exec", "-T", "paperless-test", "--user", "65534", "--group", "65534", "--",
               "pdftotext", "-layout", "-enc", "UTF-8", "-", "-"]
    return " ".join(subprocess.check_output(command, input=pdf, timeout=180).decode().split())


def protocol():
    year, issue = subprocess.check_output([*PHP, "doklad"], stdin=subprocess.DEVNULL, timeout=240).decode().split()
    if not re.fullmatch(r"20[0-9]{2}", year) or not re.fullmatch(r"[0-9a-f]{64}", issue):
        raise ValueError("Moodle vrátil neplatné vydání.")
    cert = PROOF / f"akademie-osvedceni-{issue}.pdf"
    with cert.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    # Vazbu na osvědčení kontrolujeme přímo proti archivu z téhož vydání.
    uloz_a_over_pdf(cert, digest, int(year))
    scores = json.loads((PROOF / "akademie-znamky.json").read_text())
    answer = json.loads(subprocess.check_output([*PHP, "komise"], input=json.dumps(
        dict(scores, osvedceni=digest)).encode(), timeout=240))
    record = answer["udaje"]
    unsigned = base64.b64decode(answer["pdf"], validate=True)
    labels = pdf_text(unsigned)
    if (record["vydani"] != issue or record["osvedceni_sha256"] != digest or record["rezim"] != "TEST"
            or record["procent"] != 100 or len(set(record["komise"])) != 3
            or not all(v in labels for v in ["VZOR TEST", "TEST A", "100 %", digest, *record["komise"]])):
        raise ValueError("Text komisního protokolu neodpovídá výsledku a složení komise.")

    target = PROOF / f"akademie-komise-{issue}.pdf"
    signed = target.read_bytes() if target.exists() else pecet.call(65534, "--pecet", "cvicny-protokol-komise", data=unsigned)
    ca = pecet.call(65534, "--verejny-koren").decode().strip()
    pecet.call(65533, "--overit", data=json.dumps({"pdf": base64.b64encode(signed).decode(), "ca": ca}).encode())
    if pdf_text(signed) != labels:
        raise ValueError("Zapečetěný protokol má jiný obsah než dnešní podklady z Moodle.")
    if not target.exists():
        atomic(target, signed)
    sealed_digest = hashlib.sha256(signed).hexdigest()
    uloz_a_over_pdf(target, sealed_digest, int(record["provedeno"][:4]))
    for path, checksum in ((cert, digest), (target, sealed_digest)):
        with path.open("rb") as stream:
            subprocess.run(["incus", "exec", "-T", "reditelstvi-test", "--", "sh", "-ec", """
                dir=/usr/local/share/polarita-akademie-doklady
                mkdir -p "$dir"
                tmp=$(mktemp "$dir/.doklad-XXXXXXXX")
                trap 'rm -f -- "$tmp"' EXIT
                cat >"$tmp"
                test "$(sha256sum "$tmp" | cut -d' ' -f1)" = "$1"
                chmod 0644 "$tmp"
                mv -f "$tmp" "$dir/$1.pdf"
            """, "doklad", checksum], stdin=stream, check=True, timeout=120)
    subprocess.run(["incus", "exec", "-T", "reditelstvi-test", "--", "sh", "-ec", """
        dir=/usr/local/share/polarita-akademie-doklady
        printf '%s.pdf\n' "$1" > "$dir/.komise-next"
        chmod 0644 "$dir/.komise-next"
        mv -f "$dir/.komise-next" "$dir/komise"
    """, "doklad", sealed_digest], stdin=subprocess.DEVNULL, check=True)
    record["protokol_sha256"] = sealed_digest
    atomic(PROOF / "akademie-komise.json", json.dumps(record, ensure_ascii=False, sort_keys=True).encode())
    print(f"Tříčlenná cvičná komise má protokol výsledku Moodle s místní pečetí a ověřeným časovým razítkem. "
          f"Archivní snímek obsahuje shodné PDF pod SHA-256 {sealed_digest}.")


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Komisní protokol patří do TEST ředitelství.")
    with open("/run/polarita-akademie-vydani.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        protocol()
