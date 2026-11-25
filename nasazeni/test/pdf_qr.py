"""Sazba Typst a optické přečtení kódu v již nasazených službách ředitelství."""
import json

from inzenyring.revize.publikace import run

QR = """import sys, zxingcpp
code = zxingcpp.create_barcode(sys.argv[1], zxingcpp.BarcodeFormat.QRCode)
print(zxingcpp.write_barcode_to_svg(code))
"""


def vytiskni(sablona, model, zprava):
    svg = run("paperless-test", "python3", "-c", QR, zprava, user="65534").decode()
    return run("reditelstvi-test", "/usr/local/bin/polarita-typst", "compile", "--ignore-system-fonts",
               "--creation-timestamp", "0", "--root", "/usr/local/share/polarita-revize-test",
               "--input", "model="+json.dumps({**model, "qr": svg}, ensure_ascii=False),
               "-", "-", user="65534", data=sablona.read_bytes())


def precti(pdf):
    return run("paperless-test", "python3", "/usr/local/share/polarita-qr.py",
               user="65534", data=pdf).decode().strip()
