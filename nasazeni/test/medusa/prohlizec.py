"""Ověří vstup do skladu z ředitelství i použití přihlašovací cookie správního webu."""
import re
import sys
from playwright.sync_api import expect, sync_playwright

host = sys.argv[1]
if not re.fullmatch(r"[a-z0-9-]+(?:[.][a-z0-9-]+)+[.]ts[.]net", host):
    sys.exit("Neplatná testovací adresa.")
origin = "https://" + host
shop = origin + ":8450"
password = sys.stdin.readline().rstrip("\r\n")
if not password:
    sys.exit("Chybí heslo testovacího správce.")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        page = browser.new_page(locale="cs-CZ")
        page.set_default_timeout(90000)
        page.goto(origin, wait_until="domcontentloaded")
        page.locator("#u").fill("spravce")
        page.locator("#p").fill(password)
        page.locator("form button").click()
        link = page.get_by_role("link", name="Otevřít správu e-shopu a kabelové bubny")
        expect(link).to_have_attribute("href", shop + "/app/")
        link.click()
        page.wait_for_url(re.compile(re.escape(shop) + r"/app/login(?:[/?#].*)?$"))
        page.locator('input[name="email"]').fill("spravce@polarita.test")
        page.locator('input[name="password"]').fill(password)
        page.locator('form button[type="submit"]').click()
        link = page.get_by_role("link", name="Kabelové bubny", exact=True)
        link.click()
        expect(page.get_by_role("heading", name="Kabelové bubny")).to_be_visible()
        label = "TEST-PREJIMKA-BUBEN-01"
        page.get_by_label("Štítek bubnu", exact=True).fill(label)
        page.get_by_role("button", name="Načíst buben").click()
        expect(page.get_by_role("heading", name=label)).to_be_visible()
        for title, amount in (("Skladem","54,75 m"),("Rezervováno","0 m"),("Volně","54,75 m")):
            expect(page.locator("dl div").filter(has=page.get_by_text(title, exact=True)).locator("dd")).to_have_text(amount)
        print("Chromium prošel přihlášením od ředitelství do Medusy. Po vyhledání štítku ukázal sklad 54,75 m "
              "skladem, nulu rezervovanou a 54,75 m k dispozici.")
    finally:
        browser.close()
