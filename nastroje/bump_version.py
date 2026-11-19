# -*- coding: utf-8 -*-
"""
Change the version of the blueprint in the canon, all documents, packages and PDF builders.
Změní verzi návrhu v kanonu, všech dokumentech, balíčcích a generátorech PDF.

EN: Replaces "Verze / Verzi / Verzí / VERZE / Version <old>" and "Polarita-<old>" by the new version in every
    text file except the files listed in kanon.json -> version_allowlist_files (they describe
    history). Afterwards run check_consistency.py and rebuild the PDFs.
CZ: Nahradí „Verze / Verzi / Verzí / VERZE / Version <stará>“ a „Polarita-<stará>“ novou verzí ve všech
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
SKIP_PARTS = {".git", "__pycache__", "vystup", "output", "audio", ".venv", "venv", "node_modules", "scratch"}
SKIP_FILES = {"test_check_consistency.py", "bump_version.py"}
SUFFIXES = (".md", ".py", ".json", ".yaml", ".yml", ".html", ".sql", ".ts")


def bump_canon(raw: str, old: str, new: str) -> str:
    """Update version and release_tag inside kanon.json cleanly and verify both changed."""
    ver_pat = re.compile(r'("version"\s*:\s*")' + re.escape(old) + r'(")')
    tag_pat = re.compile(r'("release_tag"\s*:\s*"Polarita-)' + re.escape(old) + r'(")')
    raw_v, v_count = ver_pat.subn(rf"\g<1>{new}\2", raw)
    raw_t, t_count = tag_pat.subn(rf"\g<1>{new}\2", raw_v)
    if v_count != 1 or t_count != 1:
        raise RuntimeError(f"failed to update kanon.json uniquely (version matches={v_count}, tag matches={t_count})")
    return raw_t


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
    pattern = re.compile(r"(Verze |Verzi |Verzí |VERZE |Version |Polarita-)" + re.escape(old) + r"(?!\.\d)(?!\d)")
    allow = set(canon["version_allowlist_files"])
    updates: list[tuple[Path, str]] = []
    occurrences = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES or SKIP_PARTS.intersection(path.relative_to(ROOT).parts):
            continue
        if path.relative_to(ROOT).as_posix() in allow or path == CANON_PATH or path.name in SKIP_FILES:
            continue
        text = path.read_bytes().decode("utf-8")
        updated, count = pattern.subn(lambda match: match.group(1) + new, text)
        if count:
            updates.append((path, updated))
            occurrences += count
    new_canon = bump_canon(CANON_PATH.read_text(encoding="utf-8"), old, new)
    for path, updated in updates:
        path.write_bytes(updated.encode("utf-8"))
    CANON_PATH.write_text(new_canon, encoding="utf-8", newline="\n")
    print(f"version {old} -> {new}: {occurrences} occurrences in {len(updates)} files; now run check_consistency.py and rebuild the PDFs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
