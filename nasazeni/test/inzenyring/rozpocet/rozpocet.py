"""Převod rozpočtu z výkazu výměr, XC4 NZ nebo sešitu Polarity."""
import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from nabidka import LIMIT, over_xml, polozky, sestav, souhrn, xml_bytes
from sesit import do_xc4, do_xlsx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("operace", choices=("z-vykazu", "do-xlsx", "do-xc4", "over"))
    parser.add_argument("vstup", type=Path)
    parser.add_argument("vystup", nargs="?", type=Path)
    args = parser.parse_args()
    if (args.operace == "over") != (args.vystup is None):
        parser.error("Převod vyžaduje cílový soubor, ověření přijímá pouze vstup.")
    with args.vstup.open("rb") as f:
        raw = f.read(2 * LIMIT + 1)
    if len(raw) > 2 * LIMIT:
        raise ValueError("Příliš velký vstup.")
    if args.operace == "do-xlsx":
        out = do_xlsx(raw, args.schema)
    elif args.operace == "do-xc4":
        out = do_xc4(raw, args.schema)
    else:
        out = xml_bytes(sestav(json.loads(raw))) if args.operace == "z-vykazu" else raw
        root = over_xml(out, args.schema)
        rows = polozky(root)
        print(f"{len(rows)} položek · 9 skupin · {souhrn(rows)} {root.findtext('mena') or ''} bez DPH")
        if args.operace == "over":
            return
    with NamedTemporaryFile(dir=args.vystup.parent, delete=False) as staged:
        path = Path(staged.name)
        try:
            staged.write(out)
            staged.flush()
            os.fsync(staged.fileno())
            path.replace(args.vystup)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
