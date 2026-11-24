"""Přihlášení do účtu Keycloak přes ředitelství a ověření ukončení relace v Chromiu."""
import sys
from urllib.parse import urlsplit
from playwright.sync_api import expect, sync_playwright

origin = sys.argv[1].rstrip("/")
if urlsplit(origin).scheme != "https" or urlsplit(origin).path:
    sys.exit("Je potřeba HTTPS adresa ředitelství")
secret = sys.stdin.readline().rstrip("\r\n")
if not secret:
    sys.exit("Chybí testovací heslo")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        page = browser.new_page(locale="en-US")
        page.goto(origin)
        page.locator("#u").fill("spravce")
        page.locator("#p").fill(secret)
        page.locator("form button").click()
        page.locator('a[href="/identita/realms/polarita/account/"]').click()
        username = page.locator("#username")
        expect(username).to_be_visible(timeout=25000)
        username.fill("spravce")
        password = page.locator("#password")
        if not password.is_visible():
            page.locator("#kc-login").click()
        password.fill(secret)
        page.locator("#kc-login").click()
        page.wait_for_url(lambda u: "/identita/realms/polarita/account/" in u, timeout=30000)
        expect(page.get_by_text("Personal info", exact=True).first).to_be_visible(timeout=25000)
        logout = page.get_by_text("Sign out", exact=True)
        if not logout.is_visible():
            page.get_by_test_id("options-toggle").click()
        logout.click()
        confirm = page.locator("#kc-logout")
        if confirm.is_visible():
            confirm.click()
        page.goto(origin + "/identita/realms/polarita/account/")
        expect(page.locator("#username")).to_be_visible(timeout=25000)
        print("Chromium otevřel účet z ředitelství, dokončil OIDC přihlášení správce a po odhlášení vyžádal nové přihlášení.")
    finally:
        browser.close()
