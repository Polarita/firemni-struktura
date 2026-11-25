"""Odměří lomenou trasu na konkrétní straně PDF po kontrole dvou nezávislých kót."""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys

import pymupdf

# Relativní shoda měřítek pro testovací odečet z kresby.
TOLERANCE = Decimal("0.01")


def cislo(value):
    if type(value) not in (int, float, Decimal):
        raise ValueError("Souřadnice a délky musí být čísla.")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Souřadnice a délky musí být konečné.")
    return number


def merit(source, zadani):
    with source.open("rb") as stream:
        otisk = hashlib.file_digest(stream, "sha256").hexdigest()
    if otisk != zadani["sha256"]:
        raise ValueError("Kalibrace patří k jinému PDF.")
    page = zadani["strana"]
    with pymupdf.open(source) as pdf:
        if not pdf.is_pdf or type(page) is not int or not 1 <= page <= len(pdf):
            raise ValueError("Zvolená strana PDF neexistuje.")
        box = pdf[page - 1].rect
        width, height = cislo(box.width), cislo(box.height)

    def bod(pair):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Bod musí mít dvě souřadnice.")
        x, y = map(cislo, pair)
        if not (0 <= x <= width and 0 <= y <= height):
            raise ValueError("Bod leží mimo zvolenou stranu PDF.")
        return x, y

    def usek(start, end):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = (dx * dx + dy * dy).sqrt()
        if not distance:
            raise ValueError("Koncové body úseku splývají.")
        return dx, dy, distance

    scales, directions = [], []
    for ref in zadani["koty"]:
        dx, dy, length = usek(bod(ref["od"]), bod(ref["do"]))
        known = cislo(ref["mm"])
        if known <= 0:
            raise ValueError("Kóta musí mít kladnou délku.")
        scales.append(known / length)
        directions.append((dx / length, dy / length))
    if len(scales) < 2:
        raise ValueError("Chybí druhá známá kóta.")
    # Porovnej normalizované směry, aby délka nebo otočení úsečky neměnily výsledek.
    x, y = directions[0]
    if all(abs(x * dy - y * dx) <= Decimal("0.000001") for dx, dy in directions[1:]):
        raise ValueError("Kalibrace vyžaduje kóty ve dvou nezávislých směrech.")
    if max(scales) > min(scales) * (1 + TOLERANCE):
        raise ValueError("Měřítka známých kót se liší o více než jedno procento.")
    points = [bod(pair) for pair in zadani["trasa"]]
    if len(points) < 2:
        raise ValueError("Trasa musí mít začátek a konec.")
    scale = sum(scales) / len(scales)
    length = sum(usek(a, b)[2] for a, b in zip(points, points[1:])) * scale
    return {"sha256": otisk, "strana": page, "pocet_kot": len(scales),
            "mm_na_bod_pdf": str(scale), "delka_mm": str(length.quantize(Decimal("0.001")))}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("pdf", type=Path)
    cli.add_argument("zadani", type=Path)
    args = cli.parse_args()
    try:
        data = json.loads(args.zadani.read_text(), parse_float=Decimal)
        vysledek = merit(args.pdf, data)
    except (KeyError, TypeError, ValueError, InvalidOperation, OSError, RuntimeError) as error:
        sys.exit(f"FAIL_CLOSED: {error}")
    print(json.dumps(vysledek, ensure_ascii=False))
