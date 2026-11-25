"""Ověří nákup v Chromiu. Pro další pokus uchová pouze číslo syntetického košíku."""
import json
import os
from pathlib import Path
import re
import sys
from playwright.sync_api import expect, sync_playwright

host, filename = sys.argv[1:]
if not re.fullmatch(r"[a-z0-9-]+(?:[.][a-z0-9-]+)+[.]ts[.]net", host):
    sys.exit("Neplatné jméno testovacího serveru.")
origin = "https://" + host
shop = origin + ":8450"
state_file = Path(filename)
cart = state_file.read_text().strip() if state_file.exists() else ""
if cart and not re.fullmatch(r"cart_[A-Za-z0-9_]{8,}", cart):
    sys.exit("Neočekávaný identifikátor uloženého košíku.")
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    sys.exit("Chybí heslo testovacího správce.")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        context = browser.new_context(locale="cs-CZ")
        if cart:
            initial = json.dumps({"cart":cart})
            context.add_init_script("if (location.origin === " + json.dumps(shop) +
                                    ") sessionStorage.setItem('polarita-obchod-test-v1'," + json.dumps(initial) + ");")
        page = context.new_page()
        page.set_default_timeout(90000)
        page.goto(origin, wait_until="domcontentloaded")
        page.locator("#u").fill("spravce")
        page.locator("#p").fill(password)
        page.locator("form button").click()
        link = page.get_by_role("link", name="Vyzkoušet nákup v e-shopu")
        expect(link).to_have_attribute("href", shop + "/obchod/")
        link.click()
        if not cart:
            expect(page.get_by_role("heading",name="Izolační páska TEST")).to_be_visible()
            page.get_by_role("button",name="Vložit jeden kus do košíku").click()
            expect(page.locator("#kosik")).to_be_visible()
            cart = page.evaluate("JSON.parse(sessionStorage.getItem('polarita-obchod-test-v1')).cart")
            if not re.fullmatch(r"cart_[A-Za-z0-9_]{8,}",cart):
                raise ValueError("Prohlížeč nezískal skutečný košík Medusy.")
            tmp = state_file.with_suffix(".next")
            with tmp.open("w") as f:
                f.write(cart + "\n")
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(state_file)
        expect(page.locator("#kosik:visible,#potvrzeno:visible")).to_have_count(1)
        if page.locator("#kosik").is_visible():
            expect(page.locator("#doprava")).to_contain_text("Ejpovicích")
            expect(page.locator("#celkem")).to_have_text(re.compile(r"80(?:,00)?\s*Kč"))
            page.get_by_role("button",name="Odeslat testovací objednávku").click()
        expect(page.get_by_role("heading",name="Objednávka přijata")).to_be_visible()
        receipt = page.locator("#doklad").inner_text()
        if not re.fullmatch(r"Číslo [0-9]+ · 80(?:,00)?\s*Kč · osobní odběr v Ejpovicích\.", receipt):
            raise ValueError("Potvrzení neobsahuje očekávané číslo a částku.")
        print("Chromium otevřel obchod z ředitelství. Košík potvrdil testovací objednávku. " + receipt)
    finally:
        browser.close()
