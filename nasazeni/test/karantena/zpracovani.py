"""Hostitelská fronta ve firemní VM. Pouze prověřený výsledek může opustit spool."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
import time

BASE = Path("/srv/polarita/workspace/karantena")
SPOOL = Path("/srv/polarita/data/airgap-spool/test")
WORK = Path("/srv/polarita/infra/karantena-test")
NAME = "karantena-test"
JOB = re.compile(r"[0-9a-f]{32}\.(pdf|txt|wav|dxf|ifc)")


def inc(*args, timeout=125):
    return subprocess.run(["incus", *args], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=timeout).stdout


def atomic_copy(source, target, maximum, mode, expected_digest=None):
    fd = os.open(source, os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY)
    with os.fdopen(fd, "rb") as reader:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size <= maximum:
            raise ValueError("Zdroj není samostatný soubor povolené velikosti")
        size = 0
        checksum = hashlib.sha256()
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as writer:
            tmp = Path(writer.name)
            try:
                while chunk := reader.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise ValueError("Zdroj překročil velikostní limit")
                    checksum.update(chunk)
                    writer.write(chunk)
                if size != st.st_size:
                    raise ValueError("Při kopírování se změnila velikost")
                if expected_digest is not None and checksum.hexdigest() != expected_digest:
                    raise ValueError("Nesouhlasí kontrolní součet výsledku")
                os.fchmod(writer.fileno(), mode)
                writer.flush()
                os.fsync(writer.fileno())
                tmp.replace(target)
            finally:
                tmp.unlink(missing_ok=True)
    return checksum.hexdigest()


def record(job, status):
    directory = BASE / "protokoly"
    with tempfile.NamedTemporaryFile(dir=directory, mode="w", delete=False) as f:
        json.dump(status, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, directory / (job + ".json"))


def wait_receipt(path, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            fd = os.open(path, os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY)
        except FileNotFoundError:
            time.sleep(2)
            continue
        with os.fdopen(fd,"rb") as reader:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or not 0 < meta.st_size <= 4096:
                raise ValueError("Neplatný formát dokladu offline pracovníka")
            result = json.loads(reader.read(4097))
            if not isinstance(result,dict):
                raise ValueError("Neplatná struktura dokladu offline pracovníka")
            return result
    raise TimeoutError("Offline pracovník nedodal doklad v časovém limitu")


def put_token(target, token):
    with tempfile.NamedTemporaryFile(dir=target.parent, mode="w", delete=False) as stream:
        stream.write(token)
        stream.flush()
        os.fchmod(stream.fileno(),0o444)
        os.fsync(stream.fileno())
    os.replace(stream.name,target)


def over_identitu_vm():
    if inc("config", "get", NAME, "user.polarita.role").strip() != NAME.encode():
        raise RuntimeError("Chybí identita pracovní VM")


def zastav_vm():
    def zastavena():
        state = json.loads(inc("query", "/1.0/instances/" + NAME + "/state", timeout=15))
        return state["status"] == "Stopped"

    if zastavena():
        return
    try:
        inc("stop", NAME, "--timeout", "180", timeout=210)
    except subprocess.SubprocessError:
        # Při pomalém disku může klient skončit před potvrzením řádného vypnutí.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if zastavena():
                    return
            except subprocess.SubprocessError:
                pass
            time.sleep(3)
        raise


@contextmanager
def worker():
    over_identitu_vm()
    # Držíme společný zámek instalace i zpracování. Po přerušení služby obnovíme pracovní VM.
    zastav_vm()
    token = secrets.token_hex(16)
    challenge = SPOOL / "in" / ".start"
    ready = SPOOL / "out" / ".pripraveno"
    ready.unlink(missing_ok=True)
    put_token(challenge,token)
    try:
        inc("start", NAME)
        if wait_receipt(ready, 720) != {"start":token}:
            raise ValueError("Odpověď patří jinému spuštění pracovní VM")
        yield token
    finally:
        challenge.unlink(missing_ok=True)
        try:
            zastav_vm()
        finally:
            ready.unlink(missing_ok=True)


def process(source, token):
    job = source.name
    dest = SPOOL / "in" / job
    result = SPOOL / "out" / job
    receipt = result.with_name(job+".json")
    command = dest.with_name(job+".povel")
    command.unlink(missing_ok=True)
    receipt.unlink(missing_ok=True)
    result.unlink(missing_ok=True)
    digest = atomic_copy(source, dest, 64 * 1024 * 1024, 0o444)
    try:
        put_token(command,token)
        message = wait_receipt(receipt, 1620 if source.suffix in {".dxf", ".ifc"} else 1380)
        if (message.get("soubor"), message.get("start"), message.get("sha256")) != (job,token,digest):
            raise ValueError("Doklad neodpovídá souboru a spuštění pracovní VM")
        report = message.get("vysledek")
        if not isinstance(report,dict) or not isinstance(report.get("duvod"),str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,64}",report["duvod"]):
            raise ValueError("Neplatný důvod výsledku kontroly")
        state = report.get("stav")
        if any(type(report[k]) is not int for k in ("signatury_hodin","navrat") if k in report):
            raise ValueError("Neplatná metrika kontroly")
        if state == "ocisteno":
            expected = {"pdf": "pdf", "txt": "xml", "dxf": "pdf", "ifc": "pdf"}.get(source.suffix[1:])
            if expected is None or expected != report.get("typ"):
                raise ValueError("Neodpovídá formát čisté přílohy")
            out = BASE / "vysledky" / (source.stem + "." + expected)
            output_hash = report.get("otisk_vystupu")
            if not isinstance(output_hash,str) or not re.fullmatch(r"[0-9a-f]{64}",output_hash):
                raise ValueError("Chybí otisk výsledku")
            atomic_copy(result, out, 128 * 1024 * 1024, 0o600, expected_digest=output_hash)
        elif state not in ("ceka", "odmitnuto"):
            raise ValueError("Neznámý výsledek kontroly")
        archive = {"ocisteno": "prijate", "odmitnuto": "odmitnute", "ceka": "ceka"}[state]
        safe_report = {k: report[k] for k in ("stav", "duvod", "typ", "signatury_hodin", "navrat") if k in report}
        safe_report["otisk_vstupu"] = digest
        if state == "ocisteno":
            safe_report["otisk_vystupu"] = output_hash
        record(job, safe_report)
        source.replace(BASE / archive / job)
        print(job, state, safe_report["duvod"], flush=True)
    finally:
        command.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        result.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)


def pending():
    now = time.time()
    for job in (BASE / "ceka").iterdir():
        if not JOB.fullmatch(job.name):
            continue
        report = BASE / "protokoly" / (job.name + ".json")
        if not report.is_file() or now - report.stat().st_mtime < 3600:
            continue
        why = json.loads(report.read_text()).get("duvod")
        if why != "ceka-na-offline-prepis":
            job.replace(BASE / "vstup" / job.name)


def main():
    if socket.gethostname().split(".")[0] != "polarita-hq" or os.geteuid() != 0:
        raise SystemExit("Fronta patří do polarita-hq")
    if sys.argv[1:] == ["--zastav-vm"]:
        over_identitu_vm()
        zastav_vm()
        return
    os.umask(0o077)
    for name in ("vstup", "vysledky", "protokoly", "prijate", "odmitnute", "ceka"):
        (BASE / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    with (WORK / ".instalace").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if "--opakovat" in sys.argv:
            pending()
        jobs = [p for p in sorted((BASE / "vstup").iterdir()) if JOB.fullmatch(p.name)]
        if jobs:
            with Path("/run/polarita-test-zatez.lock").open("a") as capacity:
                fcntl.flock(capacity, fcntl.LOCK_EX)
                with worker() as token:
                    for job in jobs:
                        try:
                            process(job, token)
                        except (OSError, ValueError, subprocess.SubprocessError) as err:
                            # Do zprávy se nikdy nezapisuje obsah přílohy ani výpis cizího programu.
                            record(job.name, {"stav": "ceka", "duvod": "chyba-zpracovani", "chyba": type(err).__name__})
                            job.replace(BASE / "ceka" / job.name)
                            print(job.name, "ceka", type(err).__name__, flush=True)


if __name__ == "__main__":
    main()
