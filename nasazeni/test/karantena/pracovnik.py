"""Jedna příloha v offline VM. Antivir předchází každému dalšímu čtení obsahu."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
from xml.etree.ElementTree import Element, tostring


def run(args, timeout=120, env=None):
    return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, env=env)


def result(state, reason, **fields):
    print(json.dumps(dict(stav=state, duvod=reason, **fields), ensure_ascii=False))


def database_age(directory):
    database = next((f for f in (directory/"daily.cld", directory/"daily.cvd") if f.is_file()), None)
    if not database:
        raise RuntimeError("Chybí denní antivirové signatury")
    with database.open("rb") as f:
        fields = f.read(512).decode("ascii").strip().split(":")
    # Poslední pole hlavičky CVD/CLD obsahuje čas vydání v sekundách od epochy.
    if fields[0] != "ClamAV-VDB":
        raise RuntimeError("Neplatná hlavička signatur")
    timestamp = int(fields[-1])
    age = datetime.now(timezone.utc).timestamp() - timestamp
    if age < -3600 or age > 7 * 86400:
        raise RuntimeError("Stáří denních signatur je mimo rozsah sedmi dní")
    return int(max(age, 0) // 3600)


def raster_only(path):
    count = run(["qpdf", "--show-npages", path])
    images = run(["pdfimages", "-list", path])
    structure = run(["qpdf", "--json", "--json-key=qpdf", "--json-stream-data=none", path])
    if count.returncode or images.returncode or structure.returncode:
        return False
    pages = int(count.stdout.strip())
    rendered = {int(line.split()[0]) for line in images.stdout.splitlines()
                if line.split() and line.split()[0].isdigit()}
    if pages < 1 or rendered != set(range(1, pages + 1)):
        return False
    prohibited = {"/JS", "/JavaScript", "/AA", "/OpenAction", "/EmbeddedFiles", "/EmbeddedFile",
                  "/Launch", "/AcroForm", "/RichMedia", "/SubmitForm"}
    def plain(node):
        if isinstance(node, dict):
            return not prohibited.intersection(node) and all(plain(v) for v in node.values())
        if isinstance(node, list):
            return all(plain(v) for v in node)
        return not isinstance(node, str) or node not in prohibited
    return plain(json.loads(structure.stdout))


def main():
    if socket.gethostname().split(".")[0] != "karantena-test" or set(os.listdir("/sys/class/net")) != {"lo"}:
        sys.exit("Kontrola musí běžet v bezsíťové pracovní VM")
    job = sys.argv[1]
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|txt|wav)", job):
        sys.exit("Chybné jméno úlohy")
    source = Path("/mnt/karantena-in") / job
    output = Path("/mnt/karantena-out") / job
    signatures = Path("/mnt/clamav-db")
    if any(run(["findmnt", "-no", "OPTIONS", "--mountpoint", path]).stdout.decode().strip().split(",").count("ro") != 1
           for path in (source.parent, signatures)):
        raise RuntimeError("Vstup nebo signatury nejsou připojeny pouze pro čtení")
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 64*1024*1024:
        result("odmitnuto", "neplatny-soubor")
        return
    try:
        age = database_age(signatures)
    except (OSError, ValueError, RuntimeError):
        result("ceka", "neoverene-nebo-stare-signatury")
        return
    scan = run(["clamscan", "--no-summary", "--database=" + str(signatures), "--alert-exceeds-max=yes",
                "--max-filesize=64M", "--max-scansize=128M", "--", source], timeout=480)
    if scan.returncode == 1:
        result("odmitnuto", "antivirovy-nalez", signatury_hodin=age)
        return
    if scan.returncode != 0 or not scan.stdout.rstrip().endswith(b": OK"):
        result("ceka", "nedokoncena-antivirova-kontrola")
        return
    if source.suffix == ".wav":
        result("ceka", "ceka-na-offline-prepis", signatury_hodin=age)
        return
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        if source.suffix == ".txt":
            if source.stat().st_size > 4*1024*1024:
                result("odmitnuto", "text-presahuje-4-MiB")
                return
            try:
                text = source.read_text("utf-8")
            except UnicodeError:
                result("odmitnuto", "text-neni-utf8")
                return
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]", text):
                result("odmitnuto", "neplatne-znaky-textu")
                return
            wrapper = Element("untrusted_inbound_comm", role="external_data")
            wrapper.text = text
            data = tostring(wrapper, encoding="utf-8", xml_declaration=True)
            typ = "xml"
        else:
            sanitized = work / "rekonstrukce.pdf"
            conversion = run(["dangerzone-cli", "--output-filename", sanitized, source], timeout=720)
            if conversion.returncode or not sanitized.is_file():
                result("ceka", "rekonstrukce-neprobehla", navrat=conversion.returncode)
                return
            if sanitized.stat().st_size > 128*1024*1024:
                result("odmitnuto", "rekonstrukce-presahuje-limit")
                return
            if run(["qpdf", "--check", sanitized]).returncode or not raster_only(sanitized):
                result("odmitnuto", "vadna-rekonstrukce")
                return
            data = sanitized.read_bytes()
            typ = "pdf"
        output.parent.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(f.name, output)
        result("ocisteno", "dokonceno", typ=typ, signatury_hodin=age)


if __name__ == "__main__":
    main()
