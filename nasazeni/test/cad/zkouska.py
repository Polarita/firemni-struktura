"""Prověř skutečnou vektorovou geometrii obou PDF ve vypnuté síti."""
from pathlib import Path
import shutil
import sys

import ezdxf
import pymupdf

from prevod import convert


def check(path, ratio):
    with pymupdf.open(path) as pdf:
        assert len(pdf) == 1 and not pdf[0].get_images(), "Chybný počet stran nebo rastrový výstup"
        assert abs(pdf[0].rect.width - 297 * 72 / 25.4) < 1 and abs(pdf[0].rect.height - 210 * 72 / 25.4) < 1
        points = []
        for drawing in pdf[0].get_drawings():
            for item in drawing["items"]:
                if item[0] == "l":
                    points.extend(item[1:3])
                elif item[0] == "re":
                    points.extend([item[1].tl, item[1].br])
                elif item[0] == "qu":
                    points.extend([item[1].ul, item[1].lr])
        if not points:
            raise ValueError(f"{path.name} neobsahuje čitelnou vektorovou geometrii.")
        x, y = zip(*points)
        box = pymupdf.Rect(min(x), min(y), max(x), max(y))
        assert box.width > 100 and box.height > 10 and pdf[0].rect.contains(box)
        assert abs(box.width / box.height - ratio) < 0.03, (path.name, box, ratio)


def main(directory):
    interfaces = {p.name for p in Path("/sys/class/net").iterdir()}
    if interfaces != {"lo"}:
        raise RuntimeError("Pracovník CAD má síťové rozhraní.")
    source = directory / "vzor.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0), (30, 0), (30, 10), (0, 10)], close=True)
    doc.saveas(source)
    shutil.copyfile(Path(__file__).with_name("vzor.ifc"), directory / "vzor.ifc")
    for extension, ratio in (("dxf", 3), ("ifc", 6)):
        target = directory / f"vzor-{extension}.pdf"
        convert(directory / f"vzor.{extension}", target)
        check(target, ratio)
        print(f"{extension.upper()}: PDF A4 obsahuje vektorový půdorys s očekávaným poměrem {ratio}:1.")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
