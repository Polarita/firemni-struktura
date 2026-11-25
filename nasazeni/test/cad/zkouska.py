"""Prověř skutečnou vektorovou geometrii obou PDF ve vypnuté síti."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import shutil
import subprocess
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
        return box


def check_calibration(path, box):
    # Známé rozměry pocházejí ze zdrojového výkresu v mm. Body odečteme z hotového PDF.
    a, b, c = map(list, (box.tl, box.tr, box.br))
    data = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "strana": 1,
            "koty": [{"od": a, "do": b, "mm": 30}, {"od": b, "do": c, "mm": 10}],
            "trasa": [a, b, c]}
    config = path.with_name("kalibrace.json")
    config.write_text(json.dumps(data))
    command = [sys.executable, str(Path(__file__).with_name("mereni.py")), str(path)]
    measured = subprocess.check_output([*command, str(config)])
    report = json.loads(measured)
    assert report["sha256"] == data["sha256"] and abs(float(report["delka_mm"]) - 40) < 0.01
    path.with_name("mereni.json").write_bytes(measured)
    for change in ({"koty": data["koty"][:1]}, {"koty": [data["koty"][0]] * 2},
                   {"sha256": "0" * 64}, {"strana": 2}, {"trasa": [[-1, 0], b]}):
        rejected = dict(data, **change)
        reject_measurement(command, path, rejected)
    stretched = deepcopy(data)
    stretched["koty"][1]["mm"] = 12
    reject_measurement(command, path, stretched)
    print("Kalibrace podle dvou nezávislých kót změřila trasu 40 mm; šest vadných zadání bylo odmítnuto.")


def reject_measurement(command, path, rejected):
    trial = path.with_name("vadne-zadani.json")
    trial.write_text(json.dumps(rejected))
    result = subprocess.run([*command, str(trial)], capture_output=True)
    assert result.returncode != 0 and not result.stdout and result.stderr.startswith(b"FAIL_CLOSED:")


def main(directory):
    interfaces = {p.name for p in Path("/sys/class/net").iterdir()}
    if interfaces != {"lo"}:
        raise RuntimeError("Pracovník CAD má síťové rozhraní.")
    source = directory / "vzor.dxf"
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    doc.modelspace().add_lwpolyline([(0, 0), (30, 0), (30, 10), (0, 10)], close=True)
    doc.saveas(source)
    shutil.copyfile(Path(__file__).with_name("vzor.ifc"), directory / "vzor.ifc")
    # R2000 má přímé kódování v LibreDWG a stejnou známou geometrii jako původní DXF.
    dwg = directory / "vzor.dwg"
    subprocess.run(["dxf2dwg", "-a", "r2000", "-o", dwg, source], stdin=subprocess.DEVNULL, check=True)
    with dwg.open("rb") as header:
        assert header.read(6) == b"AC1015", "Vzorek nemá binární hlavičku DWG R2000."
    for extension, ratio in (("dxf", 3), ("ifc", 6), ("dwg", 3)):
        target = directory / f"vzor-{extension}.pdf"
        convert(directory / f"vzor.{extension}", target)
        box = check(target, ratio)
        if extension == "dxf":
            check_calibration(target, box)
        print(f"{extension.upper()}: PDF A4 obsahuje vektorový půdorys s očekávaným poměrem {ratio}:1.")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
