"""Připraví neveřejnou přejímku důkazů 0–7 a na vyžádání předá ověřenou sadu do Vaultu."""
from collections import Counter
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tarfile

from kontrola import HOOKS, MAIL, SEALS, Refused, inspect_text

ZDROJ = Path("/srv/polarita/workspace/dukazy")
SOUKROME = Path("/srv/polarita/data/bootstrap-test")
BARVA = re.compile(r"\x1b\[[0-9;]*m")
ADRESA_TESTU = re.compile(r"^Příjemce zkouska-([0-9a-f]{12})@(polarita\.cz|example\.invalid) odmítnut \(([5][0-9]{2})\)$", re.M)


def priprav_text(cesta, data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # Dva původní zápisy z konzole Windows obsahují poškozené bajty.
        # Čitelné potvrzení přihlášení a odhlášení nevyžaduje odhad kódové stránky.
        if not re.fullmatch(r"blok-03/chrome-mourek-3\.3(?:\.2)?\.txt", cesta):
            raise
        lines = data.splitlines()
        if not (len(lines) == 5 and b"Chrome" in lines[1] and b"HTTPS" in lines[3]
                and re.search(rb"\bprihlaseni(?:, [a-z]+)* OK\b", lines[3])
                and lines[4].lower() == b"odhlaseni ok"):
            raise
        return "Chrome ve Windows. Historická zkouška potvrzuje přihlášení přes HTTPS a odhlášení.\n".encode()
    text = BARVA.sub("", text)
    if re.fullmatch(r"blok-03/(?:mx-[0-9a-f]{40}|restart-mx-[0-9.]+)\.txt", cesta):
        # Obě odpovědi ze stejné relace zůstanou navázané na skutečný SMTP test.
        matches = ADRESA_TESTU.findall(text)
        if (len(matches) == 2 and matches[0][0] == matches[1][0]
                and {m[1] for m in matches} == {"polarita.cz", "example.invalid"}):
            def odpoved(m):
                druh = "místní" if m[2] == "polarita.cz" else "externí"
                return f"Brána odmítla {druh} adresu ({m[3]})."
            text = ADRESA_TESTU.sub(odpoved, text)
    if (re.fullmatch(r"blok-04/openbao-2\.7\.3-(obraz|podpis)\.txt", cesta)
            or re.fullmatch(r"blok-06/dohled-[0-9a-f]{40}\.txt", cesta)):
        # UID vydavatele patří k technickému výstupu gpgv. Zachovej výsledek a řádek s otiskem.
        text = re.sub(r'^gpgv: Good signature from "[^"\n]*<[^<>\n]+@[^<>\n]+>"[^\n]*$',
                      "gpgv ověřil podpis vydavatele.", text, flags=re.M)
        text = re.sub(r'^gpgv:\s+aka "[^"\n]*<[^<>\n]+@[^<>\n]+>"[^\n]*\n', "", text, flags=re.M)
    if re.fullmatch(r"blok-01/predavaci-kontrola-serveru-[0-9]{8}T[0-9]{6}Z\.txt", cesta):
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if ("polarita_zfs" in line and "ssh" in line.lower() and re.search(r"\bOK\b", line)
                    and len(MAIL.findall(line)) == 1):
                lines[i] = "Předávací kontrola serveru potvrdila řádek s údaji o SSH a ZFS.\n"
        text = "".join(lines)
    inspect_text(text)
    return text.encode("utf-8")


def priprav(vystup):
    seals = set(SEALS.read_text().splitlines()) if SEALS.exists() else set()
    records = []
    obsah = vystup / "soubory"
    obsah.mkdir()
    with tempfile.TemporaryDirectory(dir=vystup) as work:
        testy = Path(work) / "sken"
        testy.mkdir()
        by_name = {}
        for i in range(8):
            blok = ZDROJ / f"blok-{i:02}"
            if blok.is_symlink() or not blok.is_dir():
                raise ValueError("Chybí zdrojový adresář bloku.")
            for p in sorted(blok.rglob("*")):
                mode = p.lstat().st_mode
                if stat.S_ISDIR(mode):
                    continue
                path = p.relative_to(ZDROJ).as_posix()
                record = {"cesta": path}
                records.append(record)
                try:
                    inspect_text(path)
                    if not stat.S_ISREG(mode):
                        raise Refused("Nepodporovaný typ souboru.")
                    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), "rb") as source:
                        raw = source.read()
                    record["zdroj_sha256"] = hashlib.sha256(raw).hexdigest()
                    pdf = p.suffix.lower() == ".pdf"
                    if pdf and record["zdroj_sha256"]+" "+p.name not in seals:
                        raise Refused("Neevidovaný PDF vzor.")
                    if not pdf and raw.lstrip().startswith(b"%PDF-"):
                        raise Refused("Přejmenované PDF.")
                    data = raw if pdf else priprav_text(path, raw)
                    target = obsah / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    name = f"{len(records)}.txt"
                    (testy/name).write_bytes(path.encode() + b"\n" + (b"" if pdf else data))
                    by_name[name] = record
                    record["cil_sha256"] = hashlib.sha256(data).hexdigest()
                    record["stav"] = "shodný" if data == raw else "převedený"
                except (Refused, UnicodeDecodeError) as err:
                    record["stav"] = str(err) if isinstance(err, Refused) else "Nerozpoznané kódování."
        report = Path(work) / "nalezy.json"
        cmd = ["/usr/bin/gitleaks", "detect", "--no-git", "--no-banner", "--redact",
               "--config", str(HOOKS/"gitleaks.toml"), "--report-path", str(report),
               "--exit-code", "23", "--source", str(testy)]
        scan = subprocess.run(cmd, cwd=testy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=150)
        if scan.returncode == 23:
            findings = json.loads(report.read_bytes())
            if not findings:
                raise RuntimeError("Chybí výsledky kontroly Gitleaks.")
            for finding in findings:
                rec = by_name[Path(finding["File"]).name]
                (obsah / rec["cesta"]).unlink(missing_ok=True)
                rec.pop("cil_sha256", None)
                rec["stav"] = "Přístupový údaj Gitleaks."
        elif scan.returncode:
            raise RuntimeError("Gitleaks nedokončil kontrolu.")
    for rec in records:
        path = obsah / rec["cesta"]
        if "cil_sha256" in rec and hashlib.sha256(path.read_bytes()).hexdigest() != rec["cil_sha256"]:
            raise RuntimeError("Pracovní kopie nesouhlasí s přejímkou.")
    (vystup/"index.json").write_text(json.dumps(records, ensure_ascii=False, indent=2)+"\n")
    return Counter(rec["stav"] for rec in records)


def predej(saved, digest):
    records = json.loads((saved/"index.json").read_bytes())
    if any("cil_sha256" not in rec for rec in records):
        raise ValueError("Předávka obsahuje nevyřešený soukromý nález.")
    dataset = "polarita_zfs/workspace"
    if subprocess.check_output(["findmnt", "-no", "SOURCE", "-T", ZDROJ], text=True).strip() != dataset:
        raise ValueError("Nesouhlasí zdrojový dataset přejímky.")
    name = "doklady-" + digest
    snap = dataset + "@" + name
    with (saved.parent/".predani.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = subprocess.check_output(["zfs", "list", "-H", "-d", "1", "-t", "snapshot",
                                           "-o", "name", dataset], text=True).splitlines()
        if snap not in existing:
            subprocess.run(["zfs", "snapshot", snap], check=True)
        source = ZDROJ.parent / ".zfs/snapshot" / name / ZDROJ.name
        paths = {p.relative_to(source).as_posix() for i in range(8)
                 for p in (source/f"blok-{i:02}").rglob("*") if not p.is_dir() or p.is_symlink()}
        if paths != {r["cesta"] for r in records}:
            raise ValueError("Zdroj se během přípravy změnil. Zopakuj přejímku.")
        password = (SOUKROME / "test-login/heslo").read_bytes().strip()
        if not password:
            raise ValueError("Chybí ověřovací údaj TEST.")
        with tempfile.TemporaryFile(dir=saved.parent) as pack:
            with tarfile.open(fileobj=pack, mode="w") as tar:
                for rec in records:
                    path = rec["cesta"]
                    if hashlib.sha256((source/path).read_bytes()).hexdigest() != rec["zdroj_sha256"]:
                        raise ValueError("Zdroj přejímky se změnil před snímkem.")
                    with (saved/"soubory"/path).open("rb") as f:
                        data = f.read()
                        if hashlib.sha256(data).hexdigest() != rec["cil_sha256"] or password in data:
                            raise ValueError("Neplatná pracovní kopie přejímky.")
                        item = tarfile.TarInfo(path)
                        item.size = len(data)
                        f.seek(0)
                        tar.addfile(item, f)
            pack.seek(0)
            result = subprocess.run(["/usr/local/bin/agent_vault", "prijmi-doklady"], stdin=pack,
                                    stdout=subprocess.PIPE, check=True)
        proof = json.loads(result.stdout)
        if proof["bloky"] != 8 or proof["overene_soubory"] != len(records):
            raise RuntimeError("Agent nepotvrdil přijetí celé sady.")
        return dict(proof, snimek=snap)


if __name__ == "__main__":
    if os.geteuid() or os.uname().nodename.split(".")[0] != "polarita-hq":
        sys.exit("Přejímka patří na polarita-hq.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predat", action="store_true", help="Ulož kompletní prověřenou sadu do Vaultu.")
    args = parser.parse_args()
    os.umask(0o077)
    if subprocess.check_output(["findmnt","-no","SOURCE","-T",SOUKROME], text=True).strip() != "polarita_zfs/data/bootstrap-test":
        sys.exit("Chybí soukromý dataset.")
    parent = SOUKROME / "prejimky-dukazu"
    parent.mkdir(mode=0o700, exist_ok=True)
    dst = Path(tempfile.mkdtemp(dir=parent, prefix="priprava-"))
    try:
        result = priprav(dst)
        digest = hashlib.sha256((dst/"index.json").read_bytes()).hexdigest()
        saved = parent / digest
        with (parent/".priprava.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if saved.exists():
                if (dst/"index.json").read_bytes() != (saved/"index.json").read_bytes():
                    raise RuntimeError("Soukromý index přejímky se změnil.")
                for file in (dst/"soubory").rglob("*"):
                    if file.is_file() and file.read_bytes() != (saved/file.relative_to(dst)).read_bytes():
                        raise RuntimeError("Uložená pracovní kopie se změnila.")
                shutil.rmtree(dst)
            else:
                dst.rename(saved)
    except BaseException:
        shutil.rmtree(dst, ignore_errors=True)
        raise
    report = {"pracovni_kopie": str(saved), "vysledek": result}
    if args.predat:
        report["predani"] = predej(saved, digest)
    print(json.dumps(report, ensure_ascii=False))
