"""Čte export TEST měřidla a normalizuje CSV, XML nebo JSON na stejné řádky."""
import csv
import io
import json
from xml.etree import ElementTree

SLOUPCE = ("projekt", "bod", "pristroj", "den", "jednotka", "hodnota")
LIMIT = 1024 * 1024


def unikat(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicitní klíč exportu.")
        obj[key] = value
    return obj


def nacti(raw, fmt):
    if not raw or len(raw) > LIMIT:
        raise ValueError("Prázdný nebo příliš velký export.")
    text = raw.decode("utf-8-sig")
    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != SLOUPCE:
            raise ValueError("Nesouhlasí hlavička CSV.")
        rows = list(reader)
    elif fmt == "xml":
        if "<!" in text or "\0" in text:
            raise ValueError("Nepovolená deklarace v XML.")
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as err:
            raise ValueError("Neplatný export XML.") from err
        if root.tag != "mereni" or root.attrib or any(el.tag != "radek" or len(el) for el in root):
            raise ValueError("Neznámá struktura XML.")
        rows = [el.attrib for el in root]
    elif fmt == "json":
        rows = json.loads(text, object_pairs_hook=unikat)
    else:
        raise ValueError("Neznámý formát měření.")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise ValueError("Neplatný počet měření.")
    for row in rows:
        if (not isinstance(row, dict) or set(row) != set(SLOUPCE)
                or any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in row.values())):
            raise ValueError("Nesouhlasí povinné údaje naměřené hodnoty.")
    return rows
