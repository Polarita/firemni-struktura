"""Vygeneruje celý popis entity do nového adresáře připraveného k nasazení."""
import argparse
from html import escape
import json
from pathlib import Path
import tempfile

from model import load, migrations, openapi, tool


def form(data):
    fields = []
    for name, field in data["fields"].items():
        if field["type"] == "integer":
            attrs = f'type="number" min="{field["minimum"]}" max="{field["maximum"]}" step="1" required'
        elif field["type"] == "boolean":
            attrs = 'type="checkbox"'
        else:
            attrs = f'type="text" maxlength="{field["maxLength"]}"'
        fields.append(f'<label>{escape(field["title"])} <input name="{name}" {attrs}></label>')
    title = escape(data["title"])
    return f"""<!doctype html>
<html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{font:1rem system-ui;max-width:36rem;margin:2rem auto;padding:0 1rem}}
label, output{{display:block;margin:1rem 0}} input:not([type=checkbox]){{width:100%;padding:.4rem;box-sizing:border-box}}</style>
<p><a href="./spisy">Spisy</a> · <a href="./zkousky">Termíny zkoušek Akademie</a></p><h1>{title}</h1><form data-entity="{data["entity"]}">{''.join(fields)}<button>Uložit</button></form>
<output aria-live="polite"></output><script src="./formular.js" defer></script></html>
"""


def generate(source, target):
    data = load(source)
    up, down = migrations(data)
    files = {"up.sql": up, "down.sql": down, "index.html": form(data),
             "formular.js": Path(__file__).with_name("formular.js").read_text()}
    for asset in ("spisy.html", "spisy.js"):
        files[asset] = Path(__file__).with_name(asset).read_text()
    for filename, value in [("entity.json", data), ("openapi.json", openapi(data)), ("tool.json", tool(data))]:
        files[filename] = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    # Porušený nebo jiný výstup nepřepisujeme. Celá sada má jednu revizi.
    if target.exists():
        if {p.name for p in target.iterdir()} == set(files) and all(
                (target / k).read_text() == v for k, v in files.items()):
            return
        raise ValueError("Výstup obsahuje jinou sadu, použijte adresář nové revize")
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        temp = Path(directory) / "data"
        temp.mkdir()
        for filename, content in files.items():
            (temp / filename).write_text(content)
        temp.rename(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    generate(args.source, args.target)
