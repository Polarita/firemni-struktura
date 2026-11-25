"""Přečte jediný QR z první strany nativního osvědčení TEST."""
from io import BytesIO
import subprocess
import sys

from PIL import Image
import zxingcpp

pdf = sys.stdin.buffer.read(8_000_001)
if not pdf.startswith(b"%PDF-") or len(pdf) > 8_000_000:
    raise ValueError("Chybí platný vstupní dokument.")
render = subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-r", "240", "-gray", "-"],
                        input=pdf, stdout=subprocess.PIPE, check=True, timeout=90)
codes = zxingcpp.read_barcodes(Image.open(BytesIO(render.stdout)), formats=zxingcpp.BarcodeFormat.QRCode)
if len(codes) != 1 or not codes[0].valid:
    raise ValueError("Na osvědčení se nepodařilo přečíst právě jeden QR kód.")
print(codes[0].text)
