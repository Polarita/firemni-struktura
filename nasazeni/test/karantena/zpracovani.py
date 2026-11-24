"""Hostitelská fronta ve firemní VM. Pouze prověřený výsledek může opustit spool."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
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
JOB = re.compile(r"[0-9a-f]{32}\.(pdf|txt|wav)")


def inc(*args, timeout=125):
    return subprocess.run(["incus", *args], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=timeout).stdout


def atomic_copy(source, target, maximum, mode):
    fd = os.open(source, os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY)
    with os.fdopen(fd, "rb") as reader:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size <= maximum:
            raise ValueError("Zdroj není samostatný soubor povolené velikosti")
        size = 0
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as writer:
            tmp = Path(writer.name)
            try:
                while chunk := reader.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise ValueError("Zdroj překročil velikostní limit")
                    writer.write(chunk)
                if size != st.st_size:
                    raise ValueError("Při kopírování se změnila velikost")
                os.fchmod(writer.fileno(), mode)
                writer.flush()
                os.fsync(writer.fileno())
                tmp.replace(target)
            finally:
                tmp.unlink(missing_ok=True)


def record(job, status):
    directory = BASE / "protokoly"
    with tempfile.NamedTemporaryFile(dir=directory, mode="w", delete=False) as f:
        json.dump(status, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, directory / (job + ".json"))


@contextmanager
def worker():
    if inc("config", "get", NAME, "user.polarita.role").strip() != NAME.encode():
        raise RuntimeError("Chybí identita pracovní VM")
    # Držíme společný zámek instalace i zpracování. Po přerušení služby obnovíme pracovní VM.
    if inc("list", NAME, "-f", "csv", "-c", "s").strip() == b"RUNNING":
        inc("stop", NAME, "--timeout", "180", timeout=210)
    inc("start", NAME)
    try:
        for _ in range(120):
            try:
                inc("exec", "-T", NAME, "--", "test", "-e", "/opt/polarita/karantena.py", timeout=5)
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                time.sleep(1)
        else:
            raise RuntimeError("Nedokončený start pracovní VM")
        yield
    finally:
        inc("stop", NAME, "--timeout", "180", timeout=210)


def process(source):
    job = source.name
    dest = SPOOL / "in" / job
    result = SPOOL / "out" / job
    atomic_copy(source, dest, 64 * 1024 * 1024, 0o444)
    result.unlink(missing_ok=True)
    try:
        raw = inc("exec", "-T", "--cwd", "/home/karantena", NAME, "--", "runuser", "-u", "karantena", "--",
                  "env", "XDG_RUNTIME_DIR=/run/user/17304", "python3", "/opt/polarita/karantena.py", job, timeout=1300)
        report = json.loads(raw)
        state = report["stav"]
        if state == "ocisteno":
            expected = {"pdf": "pdf", "txt": "xml"}.get(source.suffix[1:])
            if expected is None or expected != report["typ"]:
                raise ValueError("Neodpovídá formát čisté přílohy")
            out = BASE / "vysledky" / (source.stem + "." + expected)
            atomic_copy(result, out, 128 * 1024 * 1024, 0o600)
        elif state not in ("ceka", "odmitnuto"):
            raise ValueError("Neznámý výsledek kontroly")
        archive = {"ocisteno": "prijate", "odmitnuto": "odmitnute", "ceka": "ceka"}[state]
        safe_report = {k: report[k] for k in ("stav", "duvod", "typ", "signatury_hodin", "navrat") if k in report}
        record(job, safe_report)
        source.replace(BASE / archive / job)
        print(job, state, safe_report["duvod"], flush=True)
    finally:
        dest.unlink(missing_ok=True)
        result.unlink(missing_ok=True)


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
                with worker():
                    for job in jobs:
                        try:
                            process(job)
                        except (OSError, ValueError, subprocess.SubprocessError) as err:
                            # Do zprávy se nikdy nezapisuje obsah přílohy ani výpis cizího programu.
                            record(job.name, {"stav": "ceka", "duvod": "chyba-zpracovani", "chyba": type(err).__name__})
                            job.replace(BASE / "ceka" / job.name)
                            print(job.name, "ceka", type(err).__name__, flush=True)


if __name__ == "__main__":
    main()
