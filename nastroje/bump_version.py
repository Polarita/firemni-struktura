# -*- coding: utf-8 -*-
"""
Change the version of the blueprint in the canon, all documents, packages and PDF builders.
Změní verzi návrhu v kanonu, všech dokumentech, balíčcích a generátorech PDF.

EN: Replaces "Verze / Verzi / Verzí / VERZE <old>" and "Polarita-<old>" by the new version in every
    text file except the files listed in kanon.json -> version_allowlist_files (they describe
    history). Afterwards run check_consistency.py and rebuild the PDFs.
CZ: Nahradí „Verze / Verzi / Verzí / VERZE <stará>“ a „Polarita-<stará>“ novou verzí ve všech
    textových souborech kromě souborů v kanon.json -> version_allowlist_files (popisují historii).
    Poté spusť check_consistency.py a znovu sestav PDF.

Usage / Použití:  python nastroje/bump_version.py 2.1
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON_PATH = Path(__file__).resolve().parent / "kanon.json"
SKIP_PARTS = {".git", "__pycache__", "vystup", "output", "audio"}
SUFFIXES = (".md", ".py", ".json", ".yaml", ".yml", ".html", ".sql", ".ts")


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if len(arguments) != 1 or not re.fullmatch(r"\d+\.\d+", arguments[0]):
        print("usage: python nastroje/bump_version.py <major.minor>", file=sys.stderr)
        return 2
    new = arguments[0]
    canon = json.loads(CANON_PATH.read_text(encoding="utf-8"))
    old = canon["version"]
    if new == old:
        print(f"version is already {old}")
        return 0
    pattern = re.compile(r"(Verze |Verzi |Verzí |VERZE |Version |Polarita-)" + re.escape(old) + r"(?!\d)")
    allow = set(canon["version_allowlist_files"])
    changed = occurrences = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES or SKIP_PARTS.intersection(path.relative_to(ROOT).parts):
            continue
        if path.relative_to(ROOT).as_posix() in allow or path == CANON_PATH:
            continue
        text = path.read_bytes().decode("utf-8")
        updated, count = pattern.subn(lambda match: match.group(1) + new, text)
        if count:
            path.write_bytes(updated.encode("utf-8"))
            changed += 1
            occurrences += count
    canon["version"] = new
    canon["release_tag"] = f"Polarita-{new}"
    raw = CANON_PATH.read_text(encoding="utf-8")
    raw = raw.replace(f'"version": "{old}"', f'"version": "{new}"').replace(f'"release_tag": "Polarita-{old}"', f'"release_tag": "Polarita-{new}"')
    CANON_PATH.write_text(raw, encoding="utf-8", newline="\n")
    print(f"version {old} -> {new}: {occurrences} occurrences in {changed} files; now run check_consistency.py and rebuild the PDFs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
