"""Vyplní kopii nativního A4 archu Offline Quiz pro optickou zkoušku v TEST."""
from io import BytesIO
import subprocess
import sys

from PIL import Image, ImageDraw

# Polohy polí jsou v mm podle answer_pdf::add_answer_page a Header v Offline Quiz 5.2.
VARIANTY = {"A": ("9000001", (1, 0)), "B": ("9000002", (0, 2))}
label, = sys.argv[1:]
number, answers = VARIANTY[label]
source = sys.stdin.buffer.read(8_000_001)
if not source.startswith(b"%PDF-") or len(source) > 8_000_000:
    raise ValueError("Chybí tiskový arch Offline Quiz.")
raster = subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-r", "300", "-gray", "-"],
                        input=source, stdout=subprocess.PIPE, check=True, timeout=60)
image = Image.open(BytesIO(raster.stdout)).convert("L")
if abs(image.width - 2480) > 2 or abs(image.height - 3508) > 2:
    raise ValueError("Arch nemá očekávaný formát A4.")
draw = ImageDraw.Draw(image)
scale = 300 / 25.4


def cross(x, y):
    for a, b in [(0.35, 3.15), (3.15, 0.35)]:
        draw.line(((x + a) * scale, (y + 0.35) * scale, (x + b) * scale, (y + 3.15) * scale),
                  fill=0, width=round(0.48 * scale))


for column, digit in enumerate(number):
    cross(139 + 6.5 * column, 44 + 6 * int(digit))
for row, choice in enumerate(answers):
    cross(22.3 + 6.5 * choice, 110.6 + 6.5 * row)
image.save(sys.stdout.buffer, "PNG", dpi=(300, 300))
