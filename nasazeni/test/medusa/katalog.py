"""Založí opakovatelnou sadu pro test objednávky výhradně přes nativní správní API."""
from urllib.parse import urlencode

FIXTURE = "polarita-objednavka-v1"
MARK = {"polarita_test": FIXTURE}


def katalog(call, token):
    def get(path, **query):
        suffix = "?" + urlencode(query) if query else ""
        return call("GET", "/admin/" + path + suffix, 200, token=token)

    def post(path, body):
        return call("POST", "/admin/" + path, 200, body, token)

    def records(path, key, **query):
        offset = 0
        while True:
            page = get(path, limit=100, offset=offset, **query)
            rows = page[key]
            yield from rows
            offset += len(rows)
            if not rows or offset >= page["count"]:
                return

    def match(rows, field, value):
        matches = [r for r in rows if r.get(field) == value]
        if len(matches) > 1:
            raise RuntimeError("Více testovacích záznamů pro " + str(value))
        return matches[0] if matches else None

    def entity(path, plural, singular, body, field="name"):
        row = match(records(path, plural, fields=f"id,{field},metadata"), field, body[field])
        if row:
            if (row.get("metadata") or {}).get("polarita_test") != FIXTURE:
                raise RuntimeError("Kolize testovacího názvu " + str(body[field]))
            return row
        return post(path, {**body, "metadata": MARK})[singular]

    stores = get("stores")["stores"]
    if len(stores) != 1:
        raise RuntimeError("Pro přípravu měn je nutný jediný obchod v samostatné Meduse TEST.")
    store = stores[0]
    currencies = [{k: c[k] for k in ("currency_code","is_default","is_tax_inclusive") if c.get(k) is not None}
                  for c in store["supported_currencies"]]
    missing = [c for c in ("czk","eur") if not any(r["currency_code"] == c for r in currencies)]
    if missing:
        post("stores/" + store["id"], {"supported_currencies": currencies + [
            {"currency_code": c, "is_default": not currencies and c == "czk"} for c in missing]})

    channel = entity("sales-channels", "sales_channels", "sales_channel", {"name": "E-shop Polarita TEST"})
    region = entity("regions", "regions", "region", {"name": "Česko TEST", "currency_code": "czk",
                    "countries": ["cz"], "payment_providers": ["pp_system_default"], "automatic_taxes": False})
    location = entity("stock-locations", "stock_locations", "stock_location", {"name": "MAIN-101 TEST",
                      "address": {"address_1": "Testovací sklad", "city": "Ejpovice", "country_code": "cz"}})
    loc = "stock-locations/" + location["id"]
    delivery_fields = "fulfillment_sets.id,fulfillment_sets.name,fulfillment_sets.service_zones.id,fulfillment_sets.service_zones.name"
    related = get(loc, fields="id,sales_channels.id,fulfillment_providers.id," + delivery_fields)["stock_location"]
    if not match(related["sales_channels"], "id", channel["id"]):
        post(loc + "/sales-channels", {"add": [channel["id"]]})
    if not match(related["fulfillment_providers"], "id", "manual_manual"):
        post(loc + "/fulfillment-providers", {"add": ["manual_manual"]})
    set_name = "Předání na skladě TEST"
    delivery = match(related["fulfillment_sets"], "name", set_name)
    if delivery is None:
        post(loc + "/fulfillment-sets", {"name": set_name, "type": "shipping"})
        updated = get(loc, fields="id," + delivery_fields)["stock_location"]
        delivery = match(updated["fulfillment_sets"], "name", set_name)
    if delivery is None:
        raise RuntimeError("Sklad neobsahuje vytvořenou expediční skupinu.")
    group = "fulfillment-sets/" + delivery["id"]
    zone_name = "Česká republika TEST"
    zone = match(delivery["service_zones"], "name", zone_name)
    if zone is None:
        result = post(group + "/service-zones", {"name": zone_name, "geo_zones": [{"type": "country","country_code": "cz"}]})
        zone = match(result["fulfillment_set"]["service_zones"], "name", zone_name)
    if zone is None:
        raise RuntimeError("Chybí česká expediční zóna.")
    profile = entity("shipping-profiles", "shipping_profiles", "shipping_profile",
                     {"name": "Osobní odběr Polarita TEST", "type": "default"})
    option = entity("shipping-options", "shipping_options", "shipping_option", {
        "name": "Vyzvednutí v Ejpovicích TEST", "service_zone_id": zone["id"], "shipping_profile_id": profile["id"],
        "provider_id": "manual_manual", "price_type": "flat",
        "type": {"label": "Osobní odběr", "description": "Převzetí testovací objednávky", "code": "odber-test"},
        "prices": [{"currency_code": c, "amount": 0} for c in ("czk","eur")],
        "rules": [{"attribute": "enabled_in_store", "operator": "eq", "value": "true"},
                  {"attribute": "is_return", "operator": "eq", "value": "false"}]})
    sku = "POL-TEST-PASKA-01"
    product = entity("products", "products", "product", {"title": "Izolační páska TEST", "handle": "izolacni-paska-test",
        "description": "Zkušební položka pro převzetí systému.", "status": "published",
        "shipping_profile_id": profile["id"], "sales_channels": [{"id": channel["id"]}],
        "options": [{"title": "Barva", "values": ["černá"]}], "variants": [{"title": "Černá", "sku": sku,
        "options": {"Barva": "černá"}, "manage_inventory": True, "allow_backorder": False,
        "prices": [{"currency_code": "czk","amount": 80}, {"currency_code": "eur","amount": 3.2}]}]}, "handle")
    item = match(records("inventory-items", "inventory_items", sku=sku), "sku", sku)
    if item is None:
        raise RuntimeError("Medusa nevytvořila skladovou kartu prodávané varianty.")
    levels = "inventory-items/" + item["id"] + "/location-levels"
    if not match(records(levels, "inventory_levels"), "location_id", location["id"]):
        post(levels, {"location_id": location["id"], "stocked_quantity": 20})
    title = "Storefront Polarita TEST v1"
    public = match(records("api-keys", "api_keys", type="publishable"), "title", title)
    if public is None:
        public = post("api-keys", {"title": title, "type": "publishable"})["api_key"]
    if public["type"] != "publishable" or public["revoked_at"]:
        raise RuntimeError("Storefront nemá aktivní publikovatelný klíč.")
    if not match(public.get("sales_channels", []), "id", channel["id"]):
        post("api-keys/" + public["id"] + "/sales-channels", {"add": [channel["id"]]})
    print("Katalog má publikovanou testovací pásku, dvě měny, osobní odběr a skladovou kartu MAIN-101.")
    return {"publishable": public["token"], "region_id": region["id"], "product_id": product["id"],
            "shipping_option_id": option["id"], "location_id": location["id"], "inventory_item_id": item["id"]}
