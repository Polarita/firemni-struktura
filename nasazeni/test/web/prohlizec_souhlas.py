"""Zkontroluje síťové požadavky reklamní brány v novém profilu prohlížeče."""
import re
import sys
from urllib.parse import urlsplit
from playwright.sync_api import expect, sync_playwright


def over(page, origin):
    web = origin + "/web-test/"
    tag = web + "reklama-test.js"
    requested = []
    page.on("request", lambda req: requested.append(req.url))

    def settings():
        panel = page.locator("#reklamni-souhlas")
        panel.locator("summary").click()
        return panel

    def states(operation, advertising):
        records = page.evaluate("""() => (window.dataLayer || []).filter(x => x[0] === 'consent')
            .map(x => [x[1], x[2]])""")
        expected = {"ad_storage": advertising, "ad_user_data": advertising,
                    "ad_personalization": advertising, "analytics_storage": "denied"}
        assert records[-1] == [operation, expected], records

    def accepted():
        page.wait_for_function("window.dataLayer.some(x => x.event === 'polarita_test_reklamni_mereni')")
        states("update", "granted")

    page.goto(web, wait_until="load")
    panel = settings()
    expect(panel.locator("output")).to_have_text("Reklamní měření je vypnuté.")
    states("default", "denied")
    assert requested.count(tag) == 0
    panel.get_by_role("button", name="Odmítnout měření").click()
    states("update", "denied")
    page.reload(wait_until="load")
    states("update", "denied")
    assert tag not in requested
    panel = settings()
    with page.expect_response(lambda res: res.url == tag and res.status == 200):
        panel.get_by_role("button", name="Povolit měření").click()
    accepted()
    page.goto(web + "prevzeti-sanonu/", wait_until="load")
    accepted()
    assert requested.count(tag) == 2
    panel = settings()
    panel.get_by_role("button", name="Odmítnout měření").click()
    states("update", "denied")
    page.reload(wait_until="load")
    states("update", "denied")
    assert requested.count(tag) == 2
    assert all(urlsplit(url).netloc == urlsplit(origin).netloc for url in requested)
    print("Chromium ověřil výchozí zákaz, odmítnutí, povolení a odvolání. Místní reklamní značka se načetla jen na dvou stránkách s uděleným souhlasem.")


if __name__ == "__main__":
    host = sys.argv[1]
    if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
        raise ValueError("Chybí název privátního vstupu TEST.")
    origin = "https://" + host
    password = sys.stdin.readline().rstrip("\r\n")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(locale="cs-CZ")
            page.set_default_timeout(90000)
            page.goto(origin, wait_until="domcontentloaded")
            page.locator("#u").fill("spravce")
            page.locator("#p").fill(password)
            page.locator("form button").click()
            page.wait_for_url(origin + "/prehled")
            over(page, origin)
        finally:
            browser.close()
