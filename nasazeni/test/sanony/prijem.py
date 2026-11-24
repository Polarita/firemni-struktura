"""Přijme PDF do privátní fronty a vrátí potvrzení s časem převzetí a termínem."""
from contextlib import contextmanager
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile
from uuid import UUID, NAMESPACE_URL, uuid5

ROOT = Path("/srv/polarita/workspace/karantena")
PENDING = ROOT / "sanony"
INCOMING = ROOT / "vstup"
REGISTER = "/srv/polarita/infra/metadata-test/sanony.sock"
LIMIT = 64 * 1024 * 1024

def sync_dir(path):
    fd = os.open(path, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

@contextmanager
def locked():
    with (PENDING / ".prijem.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield

def publish(folder):
    meta = json.loads((folder / "prijem.json").read_bytes())
    with socket.socket(socket.AF_UNIX) as conn:
        conn.settimeout(25)
        conn.connect(REGISTER)
        conn.sendall(json.dumps(meta).encode()+b"\n")
        with conn.makefile("rb") as result:
            raw = result.readline(2049)
        if not raw.endswith(b"\n") or len(raw) > 2048:
            raise RuntimeError("Registr nepotvrdil příjem")
        receipt = json.loads(raw)
    if "chyba" in receipt:
        shutil.rmtree(folder)
        sync_dir(PENDING)
        return receipt
    if receipt["priloha"] != meta["id"] or receipt["case_id"] != meta["spis"] or receipt["bajtu"] != meta["bajtu"]:
        raise RuntimeError("Potvrzení náleží jiné příloze")
    job = uuid5(NAMESPACE_URL, "polarita.test/sanony/" + meta["id"]).hex + ".pdf"
    pdf = folder / "priloha.pdf"
    # Zdroj vyřadíme při opakování právě tehdy, když předchozí předání zanechalo doklad.
    # Pracovník mezi vstupem a cílovým adresářem používá atomické přejmenování.
    if pdf.exists():
        if ((ROOT / "protokoly" / (job + ".json")).exists() or (INCOMING / job).exists()
                or any((ROOT / dest / job).exists() for dest in ("prijate", "odmitnute", "ceka"))):
            pdf.unlink()
        else:
            # Systemd zpřístupňuje frontu a příjem jako dva samostatné bind mounty.
            # Pojmenovaný vstup vznikne až po kontrole celé kopie uvnitř cílového mountu.
            with tempfile.NamedTemporaryFile(dir=INCOMING, prefix=".prijem-", delete=False) as dest:
                temporary = Path(dest.name)
                try:
                    digest = hashlib.sha256()
                    with pdf.open("rb") as source:
                        while chunk := source.read(1024**2):
                            digest.update(chunk)
                            dest.write(chunk)
                    if digest.hexdigest() != meta["sha256"] or dest.tell() != meta["bajtu"]:
                        raise RuntimeError("Obsah připravené přílohy se změnil")
                    dest.flush()
                    os.fsync(dest.fileno())
                    temporary.replace(INCOMING / job)
                finally:
                    temporary.unlink(missing_ok=True)
            sync_dir(INCOMING)
            pdf.unlink()
    shutil.rmtree(folder)
    sync_dir(PENDING)
    return receipt

class RequestError(Exception):
    def __init__(self, code):
        self.code = code

def receive(case, key, source, size):
    if not 0 < size <= LIMIT:
        raise RequestError(413)
    temp = Path(tempfile.mkdtemp(dir=PENDING, prefix=".nahravani-"))
    try:
        sha = hashlib.sha256()
        with (temp / "priloha.pdf").open("xb") as pdf:
            left = size
            while left:
                buf = source.read(min(1024**2, left))
                if not buf:
                    raise RequestError(400)
                if left == size and not buf.startswith(b"%PDF-"):
                    raise RequestError(415)
                pdf.write(buf)
                sha.update(buf)
                left -= len(buf)
            pdf.flush()
            os.fsync(pdf.fileno())
        meta = dict(spis=case, id=key, sha256=sha.hexdigest(), bajtu=size)
        with (temp / "prijem.json").open("x") as record:
            json.dump(meta, record)
            record.flush()
            os.fsync(record.fileno())
        sync_dir(temp)
        folder = PENDING / key
        with locked():
            if folder.exists():
                if json.loads((folder / "prijem.json").read_bytes()) != meta:
                    raise RequestError(409)
            else:
                os.rename(temp, folder)
                sync_dir(PENDING)
            return publish(folder)
    finally:
        if temp.exists():
            shutil.rmtree(temp)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *unused):
        pass

    def do_PUT(self):
        try:
            m = re.fullmatch(r"/(POL-[0-9]{4}-[0-9]{5})/([0-9a-f-]{36})", self.path)
            if not m or str(UUID(m[2])) != m[2]:
                raise RequestError(400)
            if self.headers.get_content_type() != "application/pdf":
                raise RequestError(415)
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch("[0-9]{1,9}", lengths[0]):
                raise RequestError(411)
            result = receive(m[1], m[2], self.rfile, int(lengths[0]))
            code = {"spis":404,"kolize":409}.get(result.get("chyba"), 200)
        except RequestError as e:
            code, result = e.code, {}
        except ValueError:
            code, result = 400, {}
        except (OSError, RuntimeError, KeyError):
            code, result = 503, {}
        body = json.dumps(result).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    os.umask(0o077)
    if sys.argv[1:] == ["--obnov"]:
        with locked():
            for folder in PENDING.iterdir():
                if re.fullmatch("[0-9a-f-]{36}", folder.name):
                    publish(folder)
    else:
        with socket.socket(fileno=0) as client:
            client.settimeout(120)
            Handler(client, ("local", 0), None)
