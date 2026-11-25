"""Vytvoř vektorový PDF půdorys modelu DXF nebo hran geometrie IFC."""
import argparse
import os
from pathlib import Path
import tempfile

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext, layout, pymupdf
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
import ifcopenshell
import ifcopenshell.geom
from ifcopenshell.util.shape import get_edges, get_vertices


def pudorys_ifc(source):
    model = ifcopenshell.open(str(source))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    drawing = ezdxf.new()
    space = drawing.modelspace()
    for element in model.by_type("IfcElement"):
        if not element.Representation:
            continue
        shape = ifcopenshell.geom.create_shape(settings, element)
        vertices = get_vertices(shape.geometry)
        for a, b in get_edges(shape.geometry):
            start, end = vertices[a][:2], vertices[b][:2]
            if tuple(start) != tuple(end):
                space.add_line(start, end)
    if not len(space):
        raise ValueError("IFC neobsahuje geometrii prvků s hranami v půdorysu.")
    return drawing


def convert(source, destination):
    suffix = source.suffix.lower()
    if suffix == ".ifc":
        drawing = pudorys_ifc(source)
    elif suffix == ".dxf":
        drawing = ezdxf.readfile(source)
    else:
        raise ValueError("Vstup musí být DXF nebo IFC.")
    if destination.suffix.lower() != ".pdf":
        raise ValueError("Výstup musí mít příponu PDF.")
    backend = pymupdf.PyMuPdfBackend()
    config = Configuration(background_policy=BackgroundPolicy.OFF, color_policy=ColorPolicy.BLACK)
    Frontend(RenderContext(drawing), backend, config=config).draw_layout(drawing.modelspace())
    page = layout.Page(297, 210, margins=layout.Margins.all(10))
    pdf = backend.get_pdf_bytes(page)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as writer:
        tmp = Path(writer.name)
        try:
            writer.write(pdf)
            writer.flush()
            os.replace(tmp, destination)
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("vstup", type=Path)
    cli.add_argument("vystup", type=Path)
    args = cli.parse_args()
    convert(args.vstup, args.vystup)
