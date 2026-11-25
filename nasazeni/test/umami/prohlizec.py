"""Ověří otevření analytiky z přehledu ředitelství v běžném Chromiu."""
import re
import sys
from playwright.sync_api import expect, sync_playwright


def main(host, password):
    if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host) or not password:
        raise ValueError("Chybí vstup VPN nebo testovací heslo.")
    origin = f"https://{host}"
    analytics = origin + ":8449"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(locale="cs-CZ")
            page.set_default_timeout(60000)
            page.goto(origin, wait_until="domcontentloaded")
            page.locator("#u").fill("spravce")
            page.locator("#p").fill(password)
            page.locator("form button").click()
            link = page.get_by_role("link", name="Otevřít návštěvnost webu v Umami")
            expect(link).to_have_attribute("href", analytics + "/")
            link.click()
            page.wait_for_url(analytics + "/login**")
            page.locator('input[autocomplete="username"]').fill("spravce")
            page.locator('input[autocomplete="current-password"]').fill(password)
            page.locator('button[type="submit"]').click()
            page.wait_for_url(lambda url: url.startswith(analytics + "/") and "/login" not in url)
            page.goto(analytics + "/websites/bd6c414c-cb6d-43e1-a9b7-6487272a450d", wait_until="domcontentloaded")
            expect(page.get_by_text("Ředitelství Polarity TEST", exact=True).first).to_be_visible(timeout=60000)
        finally:
            browser.close()
    print("Chromium otevřel odkaz z ředitelství, přihlásil správce a zobrazil přehled měřeného webu.")


if __name__ == "__main__":
    main(sys.argv[1], sys.stdin.readline().rstrip("\r\n"))
