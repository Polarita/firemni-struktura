"""Příjem zkušební objednávky z běžného zákaznického rozhraní a zpětné čtení správcem."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode

STATE = Path("/var/lib/polarita-medusa-test/objednavka-v1.json")


def save(state):
    tmp = STATE.with_suffix(".next")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)
    fd = os.open(STATE.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def objednej(call, token, fixtures):
    def store(method, path, body=None):
        return call(method, "/store/" + path, 200, body, publishable=fixtures["publishable"])

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    region = fixtures["region_id"]
    pricing = urlencode({"region_id": region, "fields": "id,variants.id,variants.sku,*variants.calculated_price"})
    product = store("GET", "products/" + fixtures["product_id"] + "?" + pricing)["product"]
    variants = [v for v in product["variants"] if v["sku"] == "POL-TEST-PASKA-01"]
    if len(variants) != 1 or variants[0]["calculated_price"]["calculated_amount"] != 80:
        raise RuntimeError("Zákazník nemá správnou variantu nebo cenu.")
    variant = variants[0]["id"]
    email = "prejimka-eshopu@polarita.test"
    if "cart" not in state:
        address = {"first_name": "Test", "last_name": "Převzetí", "address_1": "Testovací sklad", "city": "Ejpovice",
                   "postal_code": "33701", "country_code": "cz"}
        cart = store("POST", "carts", {"region_id": region, "email": email, "shipping_address": address,
                     "billing_address": address, "items": [{"variant_id": variant, "quantity": 1}]})["cart"]
        state["cart"] = cart["id"]
        save(state)
    if "order" not in state:
        endpoint = "carts/" + state["cart"]
        cart = store("GET", endpoint)["cart"]
        if cart["email"] != email or cart["region_id"] != region:
            raise RuntimeError("Záznam zkoušky odkazuje na jiný košík.")
        if not cart.get("completed_at"):
            option = fixtures["shipping_option_id"]
            if not any(s["shipping_option_id"] == option for s in cart["shipping_methods"]):
                options = store("GET", "shipping-options?" + urlencode({"cart_id": cart["id"]}))["shipping_options"]
                if not any(o["id"] == option for o in options):
                    raise RuntimeError("Zákazníkovi se nenabídl testovací osobní odběr.")
                store("POST", endpoint + "/shipping-methods", {"option_id": option})
            payment_fields = urlencode({"fields": "id,payment_collection.id,payment_collection.payment_sessions.provider_id"})
            cart = store("GET", endpoint + "?" + payment_fields)["cart"]
            collection = cart.get("payment_collection") or store("POST", "payment-collections",
                                                                 {"cart_id": cart["id"]})["payment_collection"]
            provider = "pp_system_default"
            if not any(s["provider_id"] == provider for s in collection.get("payment_sessions", [])):
                store("POST", "payment-collections/" + collection["id"] + "/payment-sessions", {"provider_id": provider})
        completed = store("POST", endpoint + "/complete", {})
        if completed.get("type") != "order":
            raise RuntimeError("Místní testovací platba nedokončila objednávku.")
        state["order"] = completed["order"]["id"]
        save(state)
    order_fields = urlencode({"fields": "id,email,currency_code,total,display_id,payment_status,items.variant_id,items.quantity"})
    order = call("GET", "/admin/orders/" + state["order"] + "?" + order_fields, 200, token=token)["order"]
    if (order["email"] != email or order["currency_code"] != "czk" or order["total"] != 80
            or len(order["items"]) != 1 or order["items"][0]["variant_id"] != variant
            or order["items"][0]["quantity"] != 1 or order["payment_status"] not in ("authorized","captured")):
        raise RuntimeError("Správce přečetl neočekávané údaje dokončené objednávky.")
    print(f'Objednávka TEST č. {order["display_id"]} prošla ze zákaznického košíku do správy. '
          f'Jedna testovací páska, 80 Kč, osobní odběr, stav místní platby {order["payment_status"]}.')
