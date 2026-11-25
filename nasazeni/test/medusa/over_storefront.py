"""Přečte živý katalog stejným publikovatelným klíčem, jaký dostane zákaznický prohlížeč."""
import http.client
import json
import re
import sys
from urllib.parse import urlencode

host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9-]+(?:[.][a-z0-9-]+)+[.]ts[.]net", host):
    sys.exit("Neplatná VPN adresa obchodu.")


def get(path, content_type, headers=None):
    conn = http.client.HTTPSConnection(host, 8450, timeout=90)
    try:
        conn.request("GET", path, headers=headers or {})
        res = conn.getresponse()
        if res.status != 200 or not res.getheader("Content-Type", "").startswith(content_type):
            raise RuntimeError(f"Obchod vrátil HTTP {res.status} nebo jiný typ obsahu pro {path.split('?')[0]}.")
        data = res.read(2 << 20)
        return json.loads(data) if content_type == "application/json" else data.decode()
    finally:
        conn.close()


page = get("/obchod/", "text/html")
if 'src="./nakup.js"' not in page or 'id="odeslat"' not in page:
    sys.exit("Stránka obchodu neposkytla formulář pro testovací objednávku.")
# Go může servírovat JavaScript s oběma registrovanými typy.
conn = http.client.HTTPSConnection(host, 8450, timeout=90)
try:
    conn.request("GET", "/obchod/nakup.js")
    script = conn.getresponse()
    if (script.status != 200 or script.getheader("Content-Type","").split(";")[0] not in
            ("application/javascript","text/javascript") or b"pp_system_default" not in script.read(1 << 20)):
        sys.exit("Na stránce se nenačetl skript místní platby.")
finally:
    conn.close()
config = get("/obchod/katalog.json", "application/json")
if set(config) != {"publishable","product_id","region_id","shipping_option_id"} or not config["publishable"].startswith("pk_"):
    sys.exit("Veřejná konfigurace obchodu obsahuje neočekávané hodnoty.")
query = urlencode({"region_id": config["region_id"], "fields": "id,title,variants.id,variants.sku,*variants.calculated_price"})
product = get("/store/products/" + config["product_id"] + "?" + query, "application/json",
              {"x-publishable-api-key": config["publishable"]})["product"]
prices = [v["calculated_price"] for v in product["variants"] if v["sku"] == "POL-TEST-PASKA-01"]
if len(prices) != 1 or prices[0]["calculated_amount"] != 80 or prices[0]["currency_code"].lower() != "czk":
    sys.exit("Cena produktu ve zveřejněném katalogu neodpovídá testovací objednávce.")
print("Stránka Astro i její nákupní formulář jsou dostupné ve VPN. Zákaznické Store API vrací cenu 80 Kč za testovací pásku.")
