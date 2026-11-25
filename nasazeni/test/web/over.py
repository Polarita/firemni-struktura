"""Ověří výstup Astro před přepnutím vydání ve firemní VM."""
from html.parser import HTMLParser
import json
from pathlib import Path
import sys


class Stranka(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.cmp = 0
        self.text = []
        self.in_schema = False
        self.schema = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "a":
            self.links.add(attr.get("href"))
        if tag == "script":
            if attr.get("src") == "/web-test/souhlas.js" and "defer" in attr and set(attr) == {"src", "defer"}:
                self.cmp += 1
                return
            if "src" in attr or attr.get("type") != "application/ld+json":
                raise ValueError("Neočekávaný spustitelný skript ve statické stránce.")
            self.in_schema = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_schema = False

    def handle_data(self, value):
        if self.in_schema:
            self.schema.extend(json.loads(value)["@graph"])
        else:
            self.text.append(value)


def over(root, ceny):
    files = {"index.html", "prevzeti-sanonu/index.html", "kalkulacka-svj/index.html", "llms.txt", "souhlas.js", "reklama-test.js", "obchod/index.html", "obchod/nakup.js"}
    found = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if found != files or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Sada veřejných souborů se liší od očekávaného výstupu Astro.")
    shop = (root/"obchod/index.html").read_text()
    if 'src="./nakup.js"' not in shop or 'id="odeslat"' not in shop:
        raise ValueError("V sestavení chybí ovládání testovacího nákupu.")
    home, transfer = Stranka(), Stranka()
    home.feed((root/"index.html").read_text())
    transfer.feed((root/"prevzeti-sanonu/index.html").read_text())
    calculator = Stranka()
    calculator.feed((root/"kalkulacka-svj/index.html").read_text())
    assert home.cmp == transfer.cmp == calculator.cmp == 1
    assert "Model roční úspory" in calculator.text
    for link in ("/web-test/kalkulacka-svj/", "/konfigurator", "/web-test/prevzeti-sanonu/"):
        assert link in home.links, link
    assert "/lhutnik-test/spisy" in transfer.links
    assert "/web-test/prevzeti-sanonu/" in (root/"llms.txt").read_text()
    published = {v["name"]: v["offers"]["price"] for v in home.schema if v["@type"] == "Service"}
    assert published == {v["label"]: v["base_monthly_per_object_hellers"] / 100 for v in ceny["mrr_tariffs"]}
    visible = " ".join(" ".join(home.text).split())
    for name, price in published.items():
        assert name in visible and format(price, ",.0f").replace(",", " ") + " Kč" in visible
    assert {"Organization", "LocalBusiness"} <= {v["@type"] for v in home.schema}
    assert any(v["@type"] == "FAQPage" and len(v["mainEntity"]) == 2 for v in transfer.schema)
    print(f"Astro zveřejnilo {len(published)} tarify podle schváleného ceníku, návod k předání PDF a llms.txt.")


if __name__ == "__main__":
    over(Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()))
