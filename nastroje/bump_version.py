# -*- coding: utf-8 -*-
"""
Change the version of the blueprint in the canon, all documents, packages and PDF builders.
Změní verzi návrhu v kanonu, všech dokumentech, balíčcích a generátorech PDF.

EN: Rewrites every mention of the blueprint version that check_consistency.py recognises
    ("Verze / Verzi / Verzí / Version <old>", also lower case and with Markdown markup, and
    "Polarita-<old>") in exactly the files the check reads, except the files listed in
    kanon.json -> version_allowlist_files (they describe history). Afterwards it runs the
    consistency check; exit code 1 means the check found errors. Then rebuild the PDFs.
CZ: Přepíše každou zmínku o verzi návrhu, kterou rozpozná check_consistency.py
    („Verze / Verzi / Verzí / Version <stará>“, i malými písmeny a s formátováním Markdownu,
    a „Polarita-<stará>“) právě v těch souborech, které kontrola čte, kromě souborů
    v kanon.json -> version_allowlist_files (popisují historii). Poté spustí kontrolu
    konzistence; návratový kód 1 znamená, že kontrola našla chyby. Potom znovu sestav PDF.

Usage / Použití:  python nastroje/bump_version.py 2.1
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import check_consistency

ROOT = check_consistency.ROOT
CANON_PATH = check_consistency.CANON_PATH


def bump_canon(raw: str, old: str, new: str) -> str:
    """Update version and release_tag inside kanon.json cleanly and verify both changed."""
    ver_pat = re.compile(r'("version"\s*:\s*")' + re.escape(old) + r'(")')
    tag_pat = re.compile(r'("release_tag"\s*:\s*"Polarita-)' + re.escape(old) + r'(")')
    raw_v, v_count = ver_pat.subn(rf"\g<1>{new}\2", raw)
    raw_t, t_count = tag_pat.subn(rf"\g<1>{new}\2", raw_v)
    if v_count != 1 or t_count != 1:
        raise RuntimeError(f"failed to update kanon.json uniquely (version matches={v_count}, tag matches={t_count})")
    return raw_t


def bump_text(text: str, old: str, new: str) -> tuple[str, int]:
    """
    EN: Replace the old version in every mention the check recognises; other numbers stay untouched.
        Non-breaking spaces and line endings of the file are preserved.
    CZ: Nahradí starou verzi v každé zmínce, kterou kontrola rozpozná; jiná čísla zůstávají.
        Nezlomitelné mezery i konce řádků souboru zůstávají zachovány.
    """
    count = 0
    # EN: Same view as the check (non-breaking space counts as a separator) without changing the bytes:
    #     the pattern is applied to a copy with plain spaces and the hits are copied back by position.
    # CZ: Stejný pohled jako kontrola (nezlomitelná mezera je oddělovač) beze změny bajtů: vzor se
    #     aplikuje na kopii s obyčejnými mezerami a zásahy se přenesou zpět podle pozice.
    view = re.sub("[\u00a0\u202f\u2007]", " ", text)
    pieces: list[str] = []
    last = 0
    for match in check_consistency.VERSION_RE.finditer(view):
        if match.group("number") != old:
            continue
        start, end = match.span("number")
        pieces.append(text[last:start])
        pieces.append(new)
        last = end
        count += 1
    pieces.append(text[last:])
    return "".join(pieces), count


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if len(arguments) != 1 or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)", arguments[0]):
        print("usage: python nastroje/bump_version.py <major.minor>   (e.g. 3.0; no leading zeros)", file=sys.stderr)
        return 2
    new = arguments[0]
    canon = json.loads(CANON_PATH.read_text(encoding="utf-8"))
    old = canon["version"]
    if new == old:
        print(f"version is already {old}")
        return 0
    allow = set(canon["version_allowlist_files"]) | check_consistency.VERSION_EXEMPT_FILES
    updates: list[tuple[Path, str]] = []
    occurrences = 0
    for path in check_consistency.all_files():
        if check_consistency.rel(path) in allow:
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue  # reported by the consistency check / ohlásí kontrola konzistence
        updated, count = bump_text(text, old, new)
        if count:
            updates.append((path, updated))
            occurrences += count
    new_canon = bump_canon(CANON_PATH.read_text(encoding="utf-8"), old, new)
    # EN: Documents first, the canon last: after an interrupted run the canon still names the old
    #     version and the script can simply be started again.
    # CZ: Nejprve dokumenty, kanon nakonec: po přerušeném běhu kanon stále uvádí starou verzi a
    #     skript lze prostě spustit znovu.
    for path, updated in updates:
        path.write_bytes(updated.encode("utf-8"))
    CANON_PATH.write_text(new_canon, encoding="utf-8", newline="\n")
    print(f"version {old} -> {new}: {occurrences} occurrences in {len(updates)} files")
    code = check_consistency.main([])
    print("now rebuild the PDFs (build_org_pdfs.py, build_software_pdfs.py, S1 generate_pdfs.py)"
          if code == 0 else "the consistency check found errors - fix them before rebuilding the PDFs")
    return code


if __name__ == "__main__":
    sys.exit(main())
