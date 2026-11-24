"""Ověření z klienta ve VPN. Čte testovací heslo ze stdin a zavře vlastní dočasný profil."""
import sys
from urllib.parse import urlsplit
from playwright.sync_api import expect, sync_playwright

origin = sys.argv[1].rstrip("/")
if urlsplit(origin).scheme != "https" or urlsplit(origin).path:
    sys.exit("Je potřeba HTTPS adresa ředitelství")
secret = sys.stdin.readline().rstrip("\r\n")
if not secret:
    sys.exit("Chybí testovací heslo")


def fill_angular(field, value):
    # Webový trezor se váže na událost input a za běhu střídá dva formuláře.
    field.evaluate("""(el,value) => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,value);
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
    }""", value)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        page = browser.new_page(locale="en-US")
        page.goto(origin)
        page.locator("#u").fill("spravce")
        page.locator("#p").fill(secret)
        page.locator("form button").click()
        page.locator('a[href="/hesla/"]').click()
        email = page.get_by_test_id("login-email-input")
        expect(email).to_be_visible()
        fill_angular(email, "spravce@polarita.test")
        page.get_by_test_id("login-continue-button").click()
        password = page.get_by_test_id("login-master-password-input")
        expect(password).to_be_visible()
        fill_angular(password, secret)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url(lambda url: "/#/setup-extension" in url or "/#/vault" in url, timeout=30000)
        if "/#/setup-extension" in page.url:
            page.get_by_role("button", name="Add it later").click()
            page.get_by_text("Skip to web app", exact=True).click()
        page.wait_for_url("**/#/vault", timeout=30000)
        for name in ("11 Vedení a governance", "12 Marketing a růst", "13 Obchod a logistika",
                     "14 Elektro služby a akademie", "15 Právo a technické normy", "16 Finance a kancelář",
                     "17 IT a bezpečnost", "18 Lidé a terénní realizace"):
            expect(page.get_by_text(name, exact=True).first).to_be_visible(timeout=15000)
        print("Chromium otevřel správce hesel z ředitelství a po přihlášení zobrazil všech osm kolekcí.")
    finally:
        browser.close()
