"""Přenáší pouze textové protokoly dokončených kroků TEST instalace."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def otisk(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def nacti(stream):
    zaznam = json.load(stream)
    data = zaznam["data"]
    if zaznam["sha256"] != otisk(data):
        raise ValueError("Nesouhlasí kontrolní součet průběhu instalace")
    for nazev, text in data["protokoly"].items():
        if not re.fullmatch(r"[a-z0-9-]+\.txt", nazev) or not isinstance(text, str):
            raise ValueError("Neplatný protokol instalace")
    return data


def uloz(soubor, data):
    # Až po načtení a ověření celého vstupu. Přerušený přenos ponechá starý bod.
    with tempfile.NamedTemporaryFile(dir=soubor.parent, delete=False) as vystup:
        novy = Path(vystup.name)
        try:
            vystup.write(json.dumps({"data": data, "sha256": otisk(data)}).encode())
            vystup.flush()
            os.fsync(vystup.fileno())
            os.replace(novy, soubor)
            adresar = os.open(soubor.parent, os.O_DIRECTORY)
            try:
                os.fsync(adresar)
            finally:
                os.close(adresar)
        finally:
            novy.unlink(missing_ok=True)


def main():
    akce, cesta, *args = sys.argv[1:]
    cesta = Path(cesta)
    if akce == "uloz":
        uloz(cesta, nacti(sys.stdin))
    elif akce == "zabal":
        cil, krok = args
        protokoly = {p.name: p.read_text() for p in sorted(cesta.glob("*.txt"))}
        data = {"cil": cil, "krok": krok, "protokoly": protokoly}
        print(json.dumps({"data": data, "sha256": otisk(data)}))
    elif akce == "obnov":
        cil, *kroky = args
        try:
            data = nacti(sys.stdin)
            if data["cil"] != cil or data["krok"] not in kroky:
                return
        except (ValueError, KeyError, TypeError, AttributeError):
            print("Chybí platný kontrolní bod, instalace prověří všechny kroky.", file=sys.stderr)
            return
        for nazev, text in data["protokoly"].items():
            (cesta / nazev).write_text(text)
        print(data["krok"])
    else:
        raise SystemExit("Neznámá akce")


if __name__ == "__main__":
    main()
