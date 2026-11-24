"""Ověří českou diakritiku v rastrovém dokumentu uvnitř skutečného obrazu Paperless."""
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

text = "Předávací protokol číslo 128"
with tempfile.TemporaryDirectory() as folder:
    image = Image.new("RGB", (1050, 160), "white")
    font_file = subprocess.check_output(["fc-match", "-f", "%{file}", "sans-serif"], text=True)
    ImageDraw.Draw(image).text((48, 32), text, font=ImageFont.truetype(font_file, 54), fill="black")
    path = Path(folder) / "protokol.png"
    image.save(path, dpi=(300, 300))
    actual = subprocess.check_output(["tesseract", str(path), "stdout", "-l", "ces", "--psm", "7"], text=True)
    if actual.strip() != text:
        raise ValueError(f"Rozpoznaný text neodpovídá předloze: {actual.strip()!r}")
    print(f"České OCR v obrazu Paperless přečetlo z rastru přesně „{text}“.")
