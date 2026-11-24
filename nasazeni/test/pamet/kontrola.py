"""Kontroluje obsah objektů Git. Do chybové zprávy nikdy nevypisuje nalezenou hodnotu."""
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import unicodedata

HOOKS = Path("/usr/local/lib/polarita/znalostni-git")
AREAS = Path("/etc/polarita/znalostni-oblasti")
SEALS = Path("/etc/polarita/znalostni-test-pecete")
FUNCTIONAL = {"spravce@polarita.test", "instalace@polarita.test", "znalosti@polarita.test"}
MAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)
PERSONAL = [
    (r"(?<!\d)\d{6}\s*/\s*\d{3,4}(?!\d)", "rodné číslo"),
    (r"(?<!\w)(?:\+|00)\s*(?:420|421)(?:[ .-]*\d){9}(?!\d)", "telefon"),
    (r"\b(?:CZ|SK)\s*\d{2}(?:\s*\d){20}(?!\d)", "bankovní spojení"),
    (r"[\"']?(?:rodné číslo|rodne_cislo|datum narození|datum_narozeni|birth_date|birthdate|"
     r"číslo občanského průkazu|osobní e-?mail|soukromý telefon|jméno a příjmení|trvalé bydliště|"
     r"jmeno_prijmeni|bydliště|adresa bydliště)[\"']?\s*[:=]\s*[\"']?[^\s\"'{}\[\],;]+", "osobní karta"),
    (r"(?:^|[\s\"'])(?:heslo|password|passwd|api[_ -]?key|client[_ -]?secret|access[_ -]?token)[\"']?"
     r"\s*[:=]\s*[\"']?[^\s\"'{}\[\],;]{4,}", "přístupový údaj"),
]
PATTERNS = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in PERSONAL]


class Refused(Exception):
    pass


def inspect_text(text):
    text = unicodedata.normalize("NFKC", text)
    if "\x00" in text or any(ord(c) < 32 and c not in "\t\n\r\f" for c in text):
        raise Refused("Obsah vyžaduje kontrolu binárního formátu.")
    if any(m.group().casefold() not in FUNCTIONAL for m in MAIL.finditer(text)):
        raise Refused("Nález osobního nebo neevidovaného e-mailu.")
    for pattern, label in PATTERNS:
        if pattern.search(text):
            raise Refused("Nález v kategorii " + label + ".")


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def entries(tree):
    raw = git("ls-files", "--stage", "-z") if tree is None else git("ls-tree", "-r", "-z", tree)
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        if tree is None:
            mode, oid, stage = meta.split()
            if stage != b"0":
                raise Refused("Index obsahuje nevyřešenou změnu.")
        else:
            mode, kind, oid = meta.split()
            if kind != b"blob":
                raise Refused("Nepovolený typ objektu.")
        yield mode, oid.decode("ascii"), name.decode("utf-8")


def scan(trees):
    areas = set(AREAS.read_text().splitlines())
    seals = set(SEALS.read_text().splitlines()) if SEALS.exists() else set()
    seen = set()
    with tempfile.TemporaryDirectory(prefix="polarita-znalosti-") as tmp:
        stage = Path(tmp)
        names = set()
        for tree in trees:
            for mode, oid, filename in entries(tree):
                path = PurePosixPath(filename)
                if not (mode == b"100644" and not path.is_absolute() and ".." not in path.parts and
                        (filename == ".gitignore" or (len(path.parts) > 1 and path.parts[0] in areas))):
                    raise Refused("Znalostní Git přijímá jen běžné soubory z deseti oblastí.")
                inspect_text(filename)
                names.add(filename)
                # Oprávnění vložit PDF platí jen pro konkrétní ověřený vzor a jméno.
                is_pdf = path.suffix.casefold() == ".pdf"
                key = (oid, path.name if is_pdf else "")
                if key in seen:
                    continue
                seen.add(key)
                raw = git("cat-file", "blob", oid)
                if is_pdf:
                    if hashlib.sha256(raw).hexdigest()+" "+path.name not in seals:
                        raise Refused("PDF neodpovídá ověřenému vzoru z testovací pečetící služby.")
                    continue
                if raw.lstrip().startswith(b"%PDF-"):
                    raise Refused("PDF musí mít evidovaný původ a příponu.")
                try:
                    text = raw.decode()
                except UnicodeDecodeError:
                    raise Refused("Obsah vyžaduje kontrolu binárního formátu.") from None
                inspect_text(text)
                (stage / f"obsah-{len(seen)}.txt").write_bytes(raw)
        if not names:
            return
        (stage/"nazvy.txt").write_text("\n".join(sorted(names)))
        res = subprocess.run(["/usr/bin/gitleaks", "detect", "--no-git", "--no-banner", "--redact",
                              "--exit-code", "23", "--config", str(HOOKS/"gitleaks.toml"),
                              "--source", str(stage)], cwd=stage, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, timeout=120)
        if res.returncode == 23:
            raise Refused("Gitleaks našel přístupový údaj.")
        if res.returncode:
            raise Refused("Gitleaks nedokončil kontrolu.")


def main():
    action, = sys.argv[1:]
    if action == "--index":
        scan([None])
    elif action == "--historie":
        scan(git("rev-list","--all").decode().splitlines())
    elif action == "--ref":
        tips = set()
        for line in sys.stdin:
            _, new, _ = line.rstrip("\n").split(" ", 2)
            if new.startswith("ref:") or not new.strip("0"):
                continue
            if not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", new):
                raise Refused("Neplatná revize.")
            tips.add(git("rev-parse", "--verify", new+"^{commit}").decode().strip())
        if tips:
            scan(git("rev-list", *sorted(tips), "--not", "--all").decode().splitlines())
    else:
        raise ValueError("Neznámý režim kontroly")


if __name__ == "__main__":
    try:
        main()
    except Refused as error:
        sys.exit(str(error))
    except (OSError, ValueError, subprocess.SubprocessError):
        sys.exit("Kontrola znalostního Git stromu se nedokončila.")
